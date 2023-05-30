from viktor import (ViktorController, 
    File,
)

from viktor.parametrization import (
    ViktorParametrization,
    GeoPointField,
    NumberField,
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


def callWindHistory(coordinates):
    #ADD clear attribution to the Copernicus program as well as a reference to Open-Meteo
    latitude = np.round(coordinates.lat,3)
    longitude = np.round(coordinates.lon,3)
    api_url = f'https://archive-api.open-meteo.com/v1/archive?latitude={latitude}&longitude={longitude}&start_date=2023-01-01&end_date=2023-01-31&hourly=temperature_2m,surface_pressure,windspeed_10m&models=best_match&timezone=auto'
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        weatherData = pd.read_json(api_url) #need to remove all the unnecessary shit
        weatherData = weatherData["hourly"]
        return weatherData
    else: 
        print("Error: failed tgo retrieve data: Code: ", response.status_code)
        

class Parametrization(ViktorParametrization):
    #Location input
    locationInput = Section('Location Inputs')
    locationInput.point = GeoPointField('Draw a point')
    #Wind turbine geometry
    geometryInput = Section('Geometry Inputs')
    geometryInput.radius = NumberField('Wind Turbine Radius [m]', default=5, min=2)
    geometryInput.height = NumberField('Wind Turbine height [m]', default=20, min=Lookup('geometryInput.radius'))
    #Performance
    performanceInput = Section('Performance Inputs')
    performanceInput.performanceCoeff = NumberField('Performance Coefficient Cp (-)', variant='slider', default=0.35, min=0.25, max=0.45, step=0.01)
    performanceInput.generatorEff = NumberField('Generator efficiency (-)', variant='slider', default=0.25, min=0.15, max=0.40, step=0.01)


class Controller(ViktorController):
    viktor_enforce_field_constraints = True 
    label = 'Wind turbine app'
    parametrization = Parametrization

    @MapView('Map view', duration_guess=1)
    def get_map_view(self, params, **kwargs):
        # Create some point using given location coordinates
        features = []
        if params.locationInput.point:
            features.append(MapPoint.from_geo_point(params.locationInput.point))
        return MapResult(features)

    @GeometryView("Geometry", up_axis='Y', duration_guess=1)
    def get_geometry_view(self, params, **kwargs):
        #load a model of the wind turbine
        geometry = File.from_path(Path(__file__).parent / "wind_turbine_model.glb")  # or .glTF
        return GeometryResult(geometry)
    
    @ImageView("Plot", duration_guess=1)
    def create_result(self, params, **kwargs):
        weather = callWindHistory(params.locationInput.point)
        print(weather)
        fig = plt.figure()
        plt.title('performance Plot')
        plt.xlabel('date')
        plt.ylabel('Power produced [kW]')
        temperature = np.array(weather[1])
        pressure = np.array(weather[2])
        windSpeed = np.array(weather[3])
        sweptArea = np.pi * ((params.geometryInput.radius)/4.)**2
        airDensity = (pressure*100/(8.314*(273.15+temperature)))*28.97 #change to airpressure formula (DBSACGPT)
        y = 0.5 * airDensity * sweptArea * params.performanceInput.performanceCoeff * ((windSpeed/3.6)**3)/1000 * params.performanceInput.generatorEff
        # save figure
        plt.plot(y)
        svg_data = StringIO()
        fig.savefig(svg_data, format='svg')
        plt.close()
        return ImageResult(svg_data)