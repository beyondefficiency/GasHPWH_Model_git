# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:51:40 2019

This module contains the actual model for the gas HPWH. It was pulled into this separate file to make it easier to maintain. This way it can
be referenced in both the simulation and validation scripts as needed.

Currently this module holds only Model_GasHPWH_MixedTank, representing a 1-node model with a fully mixed tank. The plan is to later add additional functions
for different assumptions as needed, creating a library of relevant simulation models.

@author: Peter Grant
"""

import numpy as np
import pandas as pd
import math

Minutes_In_Hour = 60 #Conversion between hours and minutes
SpecificHeat_Water = 0.998 #Btu/(lb_m-F) @ 80 deg F, http://www.engineeringtoolbox.com/water-properties-d_1508.html
Density_Water = 8.3176 #lb-m/gal @ 80 deg F, http://www.engineeringtoolbox.com/water-density-specific-weight-d_595.html
kWh_In_Wh = 1/1000 #Conversion from Wh to kWh

def Model_GasHPWH_MixedTank(Model, Parameters, Regression_COP):

    
    
    data = Model.to_numpy() #convert the dataframe to a numpy array for EXTREME SPEED!!!! (numpy opperates in C)
    col_indx = dict(zip(Model.columns, list(range(0,len(Model.columns))))) #create a dictionary to provide column index references while using numpy in following loop
    
    data[0, col_indx['Electricity CO2 Multiplier (lb/kWh)']] = Parameters[12][data[0, col_indx['Hour of Year (hr)']]]

    for i  in range(1, len(data)): #Perform the modeling calculations for each row in the index
        # 1- Calculate the jacket losses through the walls of the tank in Btu:
        data[i, col_indx['Jacket Losses (Btu)']] = -Parameters[0] * (data[i,col_indx['Tank Temperature (deg F)']] - data[i,col_indx['Ambient Temperature (deg F)']]) * (data[i,col_indx['Time (min)']] - data[i-1,col_indx['Time (min)']]) / Minutes_In_Hour
        # 2- Calculate the energy added to the tank using the backup electric resistance element, if any:
        if data[i-1, col_indx['Energy Added Backup (Btu)']] == 0:  #If the backup heating element was NOT active during the last time step, Calculate the energy added to the tank using the backup electric resistance elements
            data[i, col_indx['Energy Added Backup (Btu)']] = Parameters[1] * int(data[i, col_indx['Tank Temperature (deg F)']] < Parameters[2]) * ( data[i, col_indx['Time (min)']] - data[i-1, col_indx['Time (min)']]) / Minutes_In_Hour
        else: #If it WAS active during the last time step, Calculate the energy added to the tank using the backup electric resistance elements
            data[i, col_indx['Energy Added Backup (Btu)']] = Parameters[1] * int(data[i, col_indx['Tank Temperature (deg F)']] < Parameters[3]) * (data[i, col_indx['Time (min)']] - data[i-1, col_indx['Time (min)']]) / Minutes_In_Hour
        # 3- Calculate the energy withdrawn by the occupants using hot water:
        data[i, col_indx['Energy Withdrawn (Btu)']] = -data[i, col_indx['Hot Water Draw Volume (gal)']] * Density_Water * SpecificHeat_Water * ( data[i, col_indx['Tank Temperature (deg F)']] - data[i, col_indx['Inlet Water Temperature (deg F)']])
        # 4 - Calculate the energy added by the heat pump during the previous timestep
        data[i, col_indx['Energy Added Heat Pump (Btu)']] = (
            Parameters[4]
            * Regression_COP(data[i, col_indx['Tank Temperature (deg F)']])
            * int(data[i, col_indx['Tank Temperature (deg F)']] < (Parameters[5] - Parameters[6]) or data[i-1, col_indx['Energy Added Heat Pump (Btu)']] > 0 and data[i, col_indx['Tank Temperature (deg F)']] < Parameters[5])
            * (data[i, col_indx['Time (min)']] - data[i-1, col_indx['Time (min)']])
            / Minutes_In_Hour
            )
        # 5 - Calculate the energy change in the tank during the previous timestep
        data[i, col_indx['Total Energy Change (Btu)']] = data[i, col_indx['Jacket Losses (Btu)']] + data[i, col_indx['Energy Withdrawn (Btu)']] + data[i, col_indx['Energy Added Backup (Btu)']] + data[i, col_indx['Energy Added Heat Pump (Btu)']]
        # 6 - #Calculate the tank temperature during the final time step
        data[i, col_indx['Electricity CO2 Multiplier (lb/kWh)']] = Parameters[12][data[i, col_indx['Hour of Year (hr)']]]
        if i < len(data) - 1:
            data[i + 1, col_indx['Tank Temperature (deg F)']] = data[i, col_indx['Total Energy Change (Btu)']] / (Parameters[7]) + data[i, col_indx['Tank Temperature (deg F)']]
            
    Model = pd.DataFrame(data=data[0:,0:],index=Model.index,columns=Model.columns) #convert Numpy Array back to a Dataframe to make it more user friendly
    
    Model['COP Gas'] = Regression_COP(Model['Tank Temperature (deg F)'])
    Model['Elec Energy Demand (Watts)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Parameters[8], Parameters[9])
    Model['Electric Usage (W-hrs)'] = Model['Elec Energy Demand (Watts)'] * Model['Timestep (min)']/60 + (Model['Energy Added Backup (Btu)']/3.413)
    Model['Gas Usage (Btu)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Energy Added Heat Pump (Btu)'] / Model['COP Gas'],0)
    Model['NOx Production (ng)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Timestep (min)'] * Parameters[10], 0)
    Model['CO2 Production Gas (lb)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Timestep (min)'] * Parameters[11], 0)
    Model['CO2 Production Elec (lb)'] =  Model['Electric Usage (W-hrs)'] * kWh_In_Wh * Model['Electricity CO2 Multiplier (lb/kWh)']
    Model['CO2 Production (lb)'] = Model['CO2 Production Gas (lb)'] + Model['CO2 Production Elec (lb)']
    Model['Energy Added Total (Btu)'] = Model['Energy Added Heat Pump (Btu)'] + Model['Energy Added Backup (Btu)'] #Calculate the total energy added to the tank during this timestep
    Model['Energy Added Heat Pump (Btu/min)'] = Parameters[4] * Regression_COP(Model['Tank Temperature (deg F)'])/ Minutes_In_Hour * (Model['Energy Added Heat Pump (Btu)'] > 0)    
    
    return Model    