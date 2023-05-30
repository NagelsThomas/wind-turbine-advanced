from viktor import (ViktorController, 
    File,
)

from viktor.parametrization import (
    ViktorParametrization,
    GeoPointField,
    DynamicArray,
    NumberField,
    DateField,
    TextField,
    Section,
    Lookup,
)


from viktor.views import (
    GeometryResult, 
    GeometryView,
    ImageResult,
    ImageView,
    MapResult,
    MapPoint,
    MapView,
)

from ambiance import Atmosphere
import matplotlib.pyplot as plt
from pathlib import Path
from io import StringIO
import pandas as pd
import numpy as np
import requests
from munch import Munch


def callWindHistory(coordinates, startDate, endDate):
    #ADD clear attribution to the Copernicus program as well as a reference to Open-Meteo
    latitude = np.round(coordinates.lat,3)
    longitude = np.round(coordinates.lon,3)
    api_url = f'https://archive-api.open-meteo.com/v1/archive?latitude={latitude}&longitude={longitude}&start_date={startDate}&end_date={endDate}&hourly=temperature_2m,surface_pressure,windspeed_10m&models=best_match&timezone=auto'
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        weatherData = pd.read_json(api_url) #need to remove all the unnecessary shit
        weatherData = weatherData["hourly"]
        return weatherData
    else: 
        print("Error: failed tgo retrieve data: Code: ", response.status_code)
        
def calculateTotalEnergy(powerProduced):
    energy = np.zeros(len(powerProduced))
    for hourly in np.arange(1, len(powerProduced)):
        energy[hourly] = energy[hourly-1] + powerProduced[hourly]*3600*24/10E-6
    return energy



class Parametrization(ViktorParametrization):
    #Location input
    locationInput = Section('Location Inputs')
    locationInput.pointsArray = DynamicArray('List of your points')
    locationInput.pointsArray.name = TextField('Enter the name for your point')
    locationInput.pointsArray.point = GeoPointField('Draw a point')
    
    #Wind turbine geometry
    geometryInput = Section('Geometry Inputs')
    geometryInput.radius = NumberField('Wind Turbine Radius [m]', default=5, min=2)
    geometryInput.height = NumberField('Wind Turbine height [m]', default=20, min=Lookup('geometryInput.radius'))

    #Performance
    performanceInput = Section('Performance Inputs')
    performanceInput.performanceCoeff = NumberField('Performance Coefficient Cp (-)', variant='slider', default=0.35, min=0.25, max=0.45, step=0.01)
    performanceInput.generatorEff = NumberField('Generator efficiency (-)', variant='slider', default=0.25, min=0.15, max=0.40, step=0.01)

    #daterange
    dateInput = Section('Date range for performance')
    dateInput.startDate = DateField('Starting date')
    dateInput.endDate = DateField('Ending date')


class Controller(ViktorController):
    viktor_enforce_field_constraints = True 
    label = 'Wind turbine app'
    parametrization = Parametrization

    @MapView('Map view', duration_guess=1)
    def get_map_view(self, params: Munch, **kwargs):
        # Create some point using given location coordinates
        features = []
        for points in params.locationInput.pointsArray:
            features.append(MapPoint.from_geo_point(points.point))
        return MapResult(features)

    @GeometryView("Geometry", up_axis='Y', duration_guess=1)
    def get_geometry_view(self, params, **kwargs):
        #load a model of the wind turbine
        geometry = File.from_path(Path(__file__).parent / "wind_turbine_model.glb")  # or .glTF
        return GeometryResult(geometry)
    
    @ImageView("Plot", duration_guess=1)
    def create_result(self, params, **kwargs):
        fig, (ax1, ax2) = plt.subplots(2)
        fig.suptitle('performance Plot')
        for geoPoint in params.locationInput.pointsArray:
            weather = callWindHistory(geoPoint.point, params.dateInput.startDate, params.dateInput.endDate)
            temperature = np.array(weather[1][::24])
            pressure = np.array(weather[2][::24])
            windSpeed = np.array(weather[3][::24])
            sweptArea = np.pi * ((params.geometryInput.radius)/4.)**2
            airDensity = (pressure*100/(8.314*(273.15+temperature)))*28.97 #change to airpressure formula (DBSACGPT)
            y = 0.5 * airDensity * sweptArea * params.performanceInput.performanceCoeff * ((windSpeed/3.6)**3)/1000 * params.performanceInput.generatorEff
            totalEnergy = calculateTotalEnergy(y)
            ax1.plot(y, label=geoPoint.name)
            ax2.plot(totalEnergy)
        fig.legend()
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)