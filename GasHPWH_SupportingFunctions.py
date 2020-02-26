# -*- coding: utf-8 -*-
"""
Created on Tue Feb 25 11:43:08 2020

This script contains supporting functions that can be used to make the gas HPWH
more flexible. They are intended to enable simulations that would not be 
possible with only the base functionality included in the models. Remember
that the original model was designed to use Title 24 draw profiles and CA
mains water temperatures, calculated using CA weather data and mains
temperature formulas. These functions are intended to help the user generate
the input files needed to perform simulations outside of CA.

The first function is EnergyPlus_Weather_Reader. It reads in an EnergyPlus
weather data file, and converts it to a readable format for the user. This 
primarily means identifying the most useful columns, putting the appropriate
header on the columns, and removing the extra columns from the data set. The
columns selections match those in Big Ladder Software's Elements tool. The user
can specify whether they want the output to use 'IP' or 'SI' units. The default
it SI, and this will be returned if any unit selection other than 'IP' is
passed to the function. If 'IP' is passed, the function will perform
calculations converting from SI to IP. This function does not save the data
set, as it's anticipated that the user will pass the result into a different 
function for further analysis.

The second function is Temperature_Mains_EnergyPlus. It replicates the mains
water temperature calculation in EnergyPlus. If the user has an appropriate
weather data file this function can calculate a mains water temperature for any
climate zone. The documentation for the method can be found at
https://bigladdersoftware.com/epx/docs/8-9/engineering-reference/water-systems.html
To use this function you must have a weather data file to pass into the
function. That weather data file must have ambient temperature data for each
day of the year. The function will add a new column called 'Mains Water
Temperature (deg F)' to that data file, and populate that columns with
calculated mains temperature values. It also adds a column called 'Hour of Year
(hr)' representing the hour of the year (Assuming midnight, Jan 1 start). This
function does not save the data file, leaving the user with the flexibility of 
saving it where they desire. The algorithm has been validated by comparing it 
to the results for Chicago available in the E+ documentation This function only
works in IP units as the gas absorption HPWH simulation model is designed to
accept mains temperature data in deg F.

Current known issues:
-None!

@author: Peter Grant
"""

#%%---------------------IMPORT STATEMENTS-----------------------------------

import pandas as pd
import math
import numpy as np

#%%--------------------DEFINE FUNCTIONS-------------------------------------

def EnergyPlus_Weather_Reader(Path, Units): #When calling the function, specify the location of the desired weather file (Path) and the desired final unit system (Units)
    columns = 'Year', 'Month', 'Day', 'Hour', 'Extra-1', 'Extra-2', 'Dry Bulb Temperature (deg C)', 'Dew Point Temperature (deg C)', 'Relative Humidity (%)', 'Atmospheric Pressure (Pa)', 'Extra-3', 'Extra-4', 'Extra-5', 'Global Solar (Wh/m2)', 'Normal Solar (Wh/m2)', 'Diffuse Solar (Wh/m2)', 'c', 'd', 'e', 'f', 'g', 'Wind Speed (m/s)', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u' #Set the list of column names to use when reading the data file
    
    Data = pd.read_csv(Path, names = (columns), skiprows = [0,1,2,3,4,5,6,7]) #Read the data file, assign the column names, and skip the heder information in the first 8 rows
    
    #Delete all columns of unnecessary data
    del Data['Extra-1']
    del Data['Extra-2']
    del Data['Extra-3']
    del Data['Extra-4']
    del Data['Extra-5']
    del Data['c']
    del Data['d']
    del Data['e']
    del Data['f']
    del Data['g']
    del Data['i']
    del Data['j']
    del Data['k']
    del Data['l']
    del Data['m']
    del Data['n']
    del Data['o']
    del Data['p']
    del Data['q']
    del Data['r']
    del Data['s']
    del Data['t']
    del Data['u']
    
    #If selected by the user, convert from SI to IP units
    if Units == 'IP':
        Data['Dry Bulb Temperature (deg F)'] = 1.8 * Data['Dry Bulb Temperature (deg C)'] + 32 #Convert from deg C to deg F
        del Data['Dry Bulb Temperature (deg C)'] #Delete the old temperature column
        
        Data['Dew Point Temperature (deg F)'] = 1.8 * Data['Dew Point Temperature (deg C)'] + 32 #Convert from deg C to deg F
        del Data['Dew Point Temperature (deg C)'] #Delete the old temperature column
        
        Data['Wind Speed (ft/s)'] = Data['Wind Speed (m/s)'] * 3.28084 #Convert from m/s to ft/s
        del Data['Wind Speed (m/s)'] #Delete the old wind speed column
    
    return Data

def Temperature_Mains_EnergyPlus(Data): #Replicate the mains temperature calculations in EnergyPlus
    
    Data['Mains Temperature (deg F)'] = 0 #Create a new column in the data set for the mains water temperature. Since it hasn't been calculated yet set all values to 0
    
    Average_Outdoor_Temperature = Data['Dry Bulb Temperature (deg F)'].mean() #Calculate the average outdoor temperature over the year
    ratio = 0.4 + 0.01 * (Average_Outdoor_Temperature - 44) #Calculate the ratio used in the E+ algorithm
    lag = 35 - 1 * (Average_Outdoor_Temperature - 44) #Calculate the lag used in the E+ algorithm
    Maximum_Difference_Monthly_Average_Outdoor_Temperatures = Data.groupby('Month')['Dry Bulb Temperature (deg F)'].mean().max() - Data.groupby('Month')['Dry Bulb Temperature (deg F)'].mean().min() #Calculate the maximum difference in monthly average out door temperatures
    
    Data['Day of Year (Day)'] = np.floor(Data.index/24 + 1) #Add a new column representing the day of the year for each row
    
    for i in range(0, len(Data)):
        Data.loc[i, 'Mains Water Temperature (deg F)'] = (Average_Outdoor_Temperature + 6) + ratio * (Maximum_Difference_Monthly_Average_Outdoor_Temperatures/2) * math.sin((0.986 * (Data.loc[i, 'Day of Year (Day)'] - 15 - lag) - 90) * math.pi/180) #Calculate the mains temperature for each day and add it to the data set
    
    Data['Hour of Year (hr)'] = Data.index #Add a new column representing the hour of the year for each row
    
    return Data