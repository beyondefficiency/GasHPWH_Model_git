# -*- coding: utf-8 -*-
"""
Created on Tue Nov 19 09:51:40 2019

@author: Peter Grant
"""

import numpy as np

Minutes_In_Hour = 60
SpecificHeat_Water = 0.998 #Btu/(lb_m-F) @ 80 deg F, http://www.engineeringtoolbox.com/water-properties-d_1508.html
Density_Water = 8.3176 #lb-m/gal @ 80 deg F, http://www.engineeringtoolbox.com/water-density-specific-weight-d_595.html

def Model_GasHPWH_MixedTank(Model, Parameters, Regression_COP):
    
    for i  in range(1, len(Model.index)): #Perform the modeling calculations for each row in the index
       
        Model.loc[i, 'Jacket Losses (Btu)'] = -Parameters[0] * (Model.loc[i, 'Tank Temperature (deg F)'] - Model.loc[i, 'Ambient Temperature (deg F)']) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the jacket losses through the walls of the tank in Btu
        if Model.loc[i-1, 'Energy Added Backup (Btu)'] == 0: #If the backup heating element was NOT active during the last time step
            Model.loc[i, 'Energy Added Backup (Btu)'] = Parameters[1] * int(Model.loc[i, 'Tank Temperature (deg F)'] < Parameters[2]) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added to the tank using the backup electric resistance elements
        else: #If it WAS active during the last time step
            Model.loc[i, 'Energy Added Backup (Btu)'] = Parameters[1] * int(Model.loc[i, 'Tank Temperature (deg F)'] < Parameters[3]) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added to the tank using the backup electric resistance elements
    
        Model.loc[i, 'Energy Withdrawn (Btu)'] = -Model.loc[i, 'Hot Water Draw Volume (gal)'] * Density_Water * SpecificHeat_Water * (Model.loc[i, 'Tank Temperature (deg F)'] - Model.loc[i, 'Inlet Water Temperature (deg F)']) #Calculate the energy withdrawn by the occupants using hot water
        Model.loc[i, 'Energy Added Heat Pump (Btu)'] = Parameters[4] * Regression_COP(Model.loc[i, 'Tank Temperature (deg F)']) * int(Model.loc[i, 'Tank Temperature (deg F)'] < (Parameters[5] - Parameters[6]) or Model.loc[i-1, 'Energy Added Heat Pump (Btu)'] > 0 and Model.loc[i, 'Tank Temperature (deg F)'] < Parameters[5]) * (Model.loc[i, 'Time (min)'] - Model.loc[i-1, 'Time (min)']) / Minutes_In_Hour #Calculate the energy added by the heat pump during the previous timestep    
        Model.loc[i, 'Total Energy Change (Btu)'] = Model.loc[i, 'Jacket Losses (Btu)'] + Model.loc[i, 'Energy Withdrawn (Btu)'] + Model.loc[i, 'Energy Added Backup (Btu)'] + Model.loc[i, 'Energy Added Heat Pump (Btu)'] #Calculate the energy change in the tank during the previous timestep

        if i < len(Model.index) - 1: #Don't do this for the final timestep. Because that would summon the Knights who Say "Ni"
            Model.loc[i + 1, 'Tank Temperature (deg F)'] = Model.loc[i, 'Total Energy Change (Btu)'] / (Parameters[7]) + Model.loc[i, 'Tank Temperature (deg F)'] #Calculate the tank temperature during the next time step

    Model['COP Gas'] = Regression_COP(Model['Tank Temperature (deg F)'])
    Model['Elec Energy Demand (Watts)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Parameters[8], Parameters[9])
    Model['Electric Usage (W-hrs)'] = Model['Elec Energy Demand (Watts)'] * Model['Timestep (min)']/60 + (Model['Energy Added Backup (Btu)']/3.413)
    Model['Gas Usage (Btu)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Energy Added Heat Pump (Btu)'] / Model['COP Gas'],0)
    Model['NOx Production (ng)'] = np.where(Model['Energy Added Heat Pump (Btu)'] > 0, Model['Timestep (min)'] * Parameters[10], 0)                  
    Model['Energy Added Total (Btu)'] = Model['Energy Added Heat Pump (Btu)'] + Model['Energy Added Backup (Btu)'] #Calculate the total energy added to the tank during this timestep
    Model['Energy Added Heat Pump (Btu/min)'] = Parameters[4] * Regression_COP(Model['Tank Temperature (deg F)']) / Minutes_In_Hour * (Model['Energy Added Heat Pump (Btu)'] > 0)
    
    return Model