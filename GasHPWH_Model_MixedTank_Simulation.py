# -*- coding: utf-8 -*-
"""
Created on Mon Apr 01 12:53:33 2019

This script represents a model of GTI's gas HPWH. It is currently capable of being run using draw profile information from
either CBECC-Res or GTI's field monitoring project. It also currently has two modes, one where it simply predicts the performance
of a device over a given draw profile, and a second where it compares the performance of the device to that which is observed
in the measured data.Right now the model is capable of handling CBECC-Res draw profiles,
generated using our scripts, and data from GTI's field study on these devices.

** Update Nov. 11 2019- this is the simulation version of the script

The model is broken into several different sections. The sections are as follows:
Import Statements: Imports various python packages as necessary
Inputs: This is the most important section for the user. It includes inputs that a) Inform the model of the input data,
-(Either CBECC-Res draw profile or GTI field data), b) Determine whether it is running a simulation or comparing to measured
-data (Comparing to measured data should probably only be used for model validation purposes), and c) Define the parameters of
-the gas HPWH and the operating conditions
Constant Declarations and Calculations: This section contains constants such as the specific heat of water, as well as
-calculations needed for the project (For instance, conversions from SI units to IP)
Modeling: This section performs the calculations necessary to model the gas HPWH and, if instructed to in Inputs, compare the
-results to the measured data. This is the guts of the model, and the most important portion for users who with to truly
-understand how it functions or modify it

@author: pgrant
"""

"""
TIMING script
Updated: Nov. 13 10 PM
{using much shorter input file}
The names for each code black can be found after the "with CodeTimer(...)" statements...

USING PANDAS FOR THE PRIMARY SIMULATION CALCULATIONS:
Code block 'read from csv' took: 4.75999 ms
Code block 'initial manipulations' took: 6.04542 ms
Code block 'upper nested for loop' took: 139.07914 ms
Code block 'modeling calculations' took: 5433.06770 ms
Code block 'final changes to Model' took: 5.12562 ms
Code block 'write to csv' took: 46.22198 ms
Simulation time is 5.640758991241455

USING NUMPY FOR THE PRIMARY SIMULATION CALCULATIONS:
Code block 'read from csv' took: 3.45724 ms
Code block 'initial manipulations' took: 4.38775 ms
Code block 'upper nested for loop' took: 144.32561 ms
Code block 'modeling calculations' took: 48.67639 ms
Code block 'final changes to Model' took: 5.19892 ms
Code block 'write to csv' took: 38.57653 ms
Simulation time is 0.2520108222961426

@author: niltis
"""
#%%--------------------------IMPORT STATEMENTS--------------------------------

import pandas as pd
import numpy as np
import os
import sys
import time
import GasHPWH_Model as GasHPWH
from linetimer import CodeTimer
from datetime import datetime

ST = time.time() #begin to time the script

#%%--------------------------GAS HPWH PARAMETERS------------------------------

#These inputs are a series of constants describing the conditions of the simulation.
#The constants describing the gas HPWH itself come from communications with Alex and Paul of GTI,
#and may need to be updated if they send new values
Temperature_Tank_Initial = 115 #Deg F, initial temperature of water in the storage tank. 115 F is the standard set temperature in CBECC
Temperature_Tank_Set = 115 #Deg F, set temperature of the HPWH. 115 F is the standard set temperature in CBECC
Temperature_Tank_Set_Deadband = 10 #Deg F, deadband on the thermostat based on e-mail from Paul Glanville on Oct 31, 2019
Temperature_Water_Inlet = 40 #Deg F, inlet water temperature in this simulation. Note that this value is only used if vary_inlet_temp = False
Temperature_Ambient = 68 #Deg F, temperature of the ambient air
Volume_Tank = 65 #gal, volume of water held in the storage tank
Coefficient_JacketLoss = 2.638 #W/K, Default value from Paul Glanville on Oct 31, 2019
Power_Backup = 1250 #W, electricity consumption of the backup resistance elements
Threshold_Activation_Backup = 95 #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
Threshold_Deactivation_Backup = 105 #Deg F, sets the temperature when the backup element disengages after it has been engaged
FiringRate_HeatPump = 2930.72 #W, natural gas consumption rate when the heat pump is active
ElectricityConsumption_Active = 110 #W, electricity consumed by the fan when the heat pump is running
ElectricityConsumption_Idle = 5 #W, electricity consumed by the HPWH when idle
NOx_Output = 10 #ng/J, NOx production of the HP when active
CO2_Output_Gas = 0.0053 #metric tons/therm, CO2 production when gas absorption heat pump is active. Taken from EPA Greenhouse Gases Equivalency Calculator
CO2_Output_Electricity = 0.212115 #ton/MWh, CO2 production when the HPWH consumes electricity. Default value is the average used in California. Note that this value is only used if Vary_CO2_Elec = False
Coefficient_COP = -0.0025 #The coefficient in the COP equation
Constant_COP = 2.0341 #The constant in the COP equation

#%%--------------------------USER INPUTS------------------------------------------
# example full draw profile file name:
# “Bldg=Single_CZ=1_Wat=Hot_Prof=1_SDLM=Yes_CFA=800_Inc=FSCDB_Ver=2019.csv”.
WeatherSource = 'CA' #Type of weather file to use in the simulation. Currently, the script only supports CA weather files
Water = 'Hot' #Specify whether the input profile is hot water ('Hot') only or mixed ('Mixed') water
SDLM = 'Yes' #'Yes' or 'No' depending on whether the Standard Distribution Loss Multiplier is incorporated in the input draw profile
Building_Type = 'Single' #'Single' or 'Multi' depending on the building type of the draw profile being used
Bedrooms = 5 #Number of bedrooms used to create the draw profile. This number can range from 1 to 5
FloorArea_Conditioned = 3500 #Conditioned floor area of the dwelling used in the draw profile creation
ClimateZone = 1 #CA climate zone to use in the simulation
Include_Code = 'FSCDB' #FSCDB is the longest this can be. This defines what type of draws are included in the draw profile. Faucet, Shower, Clothes washer, Dish Washer, and Bath
Version = 2019 #States the version of the T24 draw profile data set to use. Currently, available options are 2016 and 2019

Timestep = 5 #Timestep to use in the draw profile and simulation, in minutes. The finer the timestep, the better the model, but the longer the model takes to run

vary_inlet_temp = True # enter False to fix inlet water temperature constant, and True to take the inlet water temperature from the draw profile file (to make it vary by climate zone)
Vary_CO2_Elec = True #Enter True is reading the CO2 multipliers from a data file, enter False if using the CO2 multiplier specified above

#There are two available base paths to use in the next two lines. uncomment the format you want and use it
# Path_DrawProfile_Base_Path = os.path.dirname(__file__) + os.sep + 'Data' + os.sep + 'Draw_Profiles' + os.sep
Path_DrawProfile_Base_Path = os.path.dirname(__file__) + os.sep + 'Data' + os.sep + 'Draw_Profiles'
Path_DrawProfile_File_Name = 'Bldg={0}_CZ={1}_Wat={2}_Prof={3}_SDLM={4}_CFA={5}_Inc={6}_Ver={7}.csv'.format(str(Building_Type),str(ClimateZone),str(Water),str(Bedrooms),str(SDLM),str(FloorArea_Conditioned),str(Include_Code),str(Version))
Path_DrawProfile = Path_DrawProfile_Base_Path + os.sep + Path_DrawProfile_File_Name

# Path_DrawProfile_Base_Output_Path = '/Users/nathanieliltis/Dropbox (Beyond Efficiency)/Beyond Efficiency Team Folder/Frontier - Final Absorption HPWH Simulation Scripts/Comparison to Other WHs/Individual Outputs of Simulation Model'
Path_DrawProfile_Output_Base_Path = os.path.dirname(__file__) + os.sep + 'Output'
Path_DrawProfile_Output_File_Name = 'Output_' + Path_DrawProfile_File_Name #Save the file with Output_ followed by the name of the draw profile
Path_DrawProfile_Output = Path_DrawProfile_Output_Base_Path + os.sep + Path_DrawProfile_Output_File_Name

if Vary_CO2_Elec == True: #If the user has elected to use time-varying CO2 multipliers this code will read the data set, identify the desired data, create a new data series containing the hourly multipliers for this simulation
    Folder_CO2_Elec = os.path.dirname(__file__) + os.sep + 'Data' + os.sep + 'CO2' #Specify the folder where the electric CO2 data is located
    File_CO2_Elec = r'CA2019CarbonOnly-Elec.csv' #Specify the file containing the CO2 data
    CO2_Elec = pd.read_csv(Folder_CO2_Elec + os.sep +  File_CO2_Elec, header = 2) #Read the specified data file. The header declaration is specific to the current file, and may need to be changed when using different files
    CO2_Column = 'CZ' + str(ClimateZone) + ' Electricity Long-Run Carbon Emission Factors (ton/MWh)' #Find the column name of CO2 cmultipliers for the currently used climate zone. This line will likely need to be changed if using a different file
    CO2_Output_Electricity = CO2_Elec[CO2_Column] #Create a new series holding the data for use

#%%---------------CONSTANT DECLARATIONS AND CALCULATIONS-----------------------
#COP regression calculations
Coefficients_COP = [Coefficient_COP, Constant_COP] #Combines the coefficient and the constant into an array
Regression_COP = np.poly1d(Coefficients_COP) #Creates a 1-d linear regression stating the COP of the heat pump as a function of the temperature of water in the tank

#Constants used in water-based calculations
SpecificHeat_Water = 0.998 #Btu/(lb_m-F) @ 80 deg F, http://www.engineeringtoolbox.com/water-properties-d_1508.html
Density_Water = 8.3176 #lb-m/gal @ 80 deg F, http://www.engineeringtoolbox.com/water-density-specific-weight-d_595.html

#Constants used for unit conversions
Hours_In_Day = 24 #The number of hours in a day
Minutes_In_Hour = 60 #The number of minutes in an hour
Seconds_In_Minute = 60 #The number of seconds in a minute
W_To_BtuPerHour = 3.412142 #Converting from Watts to Btu/hr
K_To_F_MagnitudeOnly = 1.8/1. #Converting from K/C to F. Only applicable for magnitudes, not actual temperatures (E.g. Yes for "A temperature difference of 10 C" but not for "The water temperature is 40 C")
Btu_In_Therm = 100000 #The number of Btus in a therm
Pounds_In_MetricTon = 2204.62 #Pounds in a metric ton
Pounds_In_Ton = 2000 #Pounds in a US ton
kWh_In_MWh = 1000 #kWh in MWh

#Calculating the NOx production rate of the HPWH when HP is active  (ng/min)
NOx_Production_Rate = NOx_Output * FiringRate_HeatPump * Seconds_In_Minute

#Calculating the CO2 production from consuming gas when the heat pump is active (lbs/min)
CO2_Production_Rate_Gas = CO2_Output_Gas * FiringRate_HeatPump * W_To_BtuPerHour * (1/Minutes_In_Hour) * (1/Btu_In_Therm) * Pounds_In_MetricTon

#Calculating the CO2 produced (lbs/kWh) by electricity consumption
#Note that this object becomes a float if Vary_C02_Elec == False but is a dataframe series if it is
CO2_Production_Rate_Electricity = CO2_Output_Electricity * Pounds_In_Ton / kWh_In_MWh
if Vary_CO2_Elec == True:
    CO2_Production_Rate_Electricity = CO2_Production_Rate_Electricity.rename_axis('CZ' + str(ClimateZone) + 'Electricity Long-Run Carbon Emission Factors (lb/kWh)')
else:
    CO2_Production_Rate_Electricity = pd.Series(data = CO2_Production_Rate_Electricity)
    CO2_Production_Rate_Electricity.repeat(8760)
    CO2_Production_Rate_Electricity.reset_index(inplace = True, drop = True)

#Converting quantities from SI units provided by Alex to (Incorrect, silly, obnoxious) IP units
Coefficient_JacketLoss = Coefficient_JacketLoss * W_To_BtuPerHour * K_To_F_MagnitudeOnly #Converts Coefficient_JacketLoss from W/K to Btu/hr-F
Power_Backup = Power_Backup * W_To_BtuPerHour #Converts to Btu/hr
FiringRate_HeatPump = FiringRate_HeatPump * W_To_BtuPerHour #Converts to Btu/hr

#Calculating the thermal mass of the water in the storage tank
ThermalMass_Tank = Volume_Tank * Density_Water * SpecificHeat_Water

#Stores the parameters describing the HPWH in a list for use in the model
Parameters = [Coefficient_JacketLoss, #0
                Power_Backup, #1
                Threshold_Activation_Backup, #2
                Threshold_Deactivation_Backup, #3
                FiringRate_HeatPump, #4
                Temperature_Tank_Set, #5
                Temperature_Tank_Set_Deadband, #6
                ThermalMass_Tank, #7
                ElectricityConsumption_Active, #8
                ElectricityConsumption_Idle, #9
                NOx_Production_Rate, #10
                CO2_Production_Rate_Gas, #11
                CO2_Production_Rate_Electricity] #12

#%%--------------------------MODELING-----------------------------------------

#A dataframe is created, based on the draw profile, in which to run the subsequent simulation
#The first step is putting the draw profile data into the right format (E.g. If it's CBECC data,
# we need to convert from event-based to timestep-based)

Draw_Profile = pd.read_csv(Path_DrawProfile) #Create a data frame called Draw_Profile containing the CBECC-Res information

Draw_Profile['Day of Year (Day)'] = Draw_Profile['Day of Year (Day)'].astype(int) #make sure the days are in integer format, not float, as a sanity check on work below
Unique_Days = Draw_Profile['Day of Year (Day)'].unique() #Identifies the number of unique days included in the draw profile
Continuous_Index_Range_of_Days = range(Draw_Profile['Day of Year (Day)'].min(), Draw_Profile['Day of Year (Day)'].max() + 1) #outlines the full time coveraeofthe data (full days)
Missing_Days = [x for x in range(Draw_Profile['Day of Year (Day)'].min(), Draw_Profile['Day of Year (Day)'].max() + 1) if x not in Unique_Days] #identifies the specific days missing

#This code creates a dataframe covering the full continuous range of draw profiles with whatever timesteps are specified and converts the CBECC-Res draw profiles into that format
Index_Model= int(len(Continuous_Index_Range_of_Days) * Hours_In_Day * Minutes_In_Hour / Timestep) #Identifies the number of timestep bins covered in the draw profile
Model = pd.DataFrame(index = range(Index_Model)) #Creates a data frame with 1 row for each bin in the draw profile
Model['Time (min)'] = Model.index * Timestep #Create a column in the data frame giving the time at the beginning of each timestep bin

Model['Hot Water Draw Volume (gal)'] = 0 #Set the default data for hot water draw volume in each time step to 0. This value will later be edited as specific flow volumes for each time step are calculated
Model['Inlet Water Temperature (deg F)'] = 0 #initialize the inlet temperature column with all 0's, to be filled in below
First_Day = Draw_Profile.loc[0, 'Day of Year (Day)'] #Identifies the day (In integer relative to 365 form, not date form) of the first day of the draw profile
Draw_Profile['Start Time of Profile (min)'] = Draw_Profile['Start time (hr)'] * Minutes_In_Hour + (Draw_Profile['Day of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the starting time of each hot water draw in Draw_Profile relative to first day of draw used
Draw_Profile['End Time of Profile (min)'] = Draw_Profile['Start time (hr)'] * Minutes_In_Hour + Draw_Profile['Duration (min)'] + (Draw_Profile['Day of Year (Day)'] - First_Day) * Hours_In_Day * Minutes_In_Hour #Identifies the ending time of each hot water draw in Draw_Profile relative to first day of draw used

for i in Draw_Profile.index: #Iterates through each draw in Draw_Profile
    Start_Time = Draw_Profile.loc[i, 'Start Time of Profile (min)'] #Reads the time when the draw starts
    End_Time = Draw_Profile.loc[i, 'End Time of Profile (min)'] #Reads the time when the draw ends
    Flow_Rate = Draw_Profile.loc[i, 'Hot Water Flow Rate (gpm)'] #Reads the hot water flow rate of the draw and stores it in the variable Flow_Rate
    Duration = Draw_Profile.loc[i, 'Duration (min)'] #Reads the duration of the draw and stores it in the variable Duration
    Water_Quantity = Flow_Rate * Duration #total draw volume is flowrate times duration

    Bin_Start = int(np.floor(Start_Time/Timestep)) #finds the model timestep bin when the draw starts, 0 indexed
    Time_First_Bin = (Bin_Start+1) * Timestep - Start_Time #first pass at flow time of draw in first bin
    if Time_First_Bin > Duration:
        Time_First_Bin = Duration #if the draw only occurs in one bin, the time at the given flow rate is limited to the total draw time.

    bin_count = 0
    while Water_Quantity > 0: #dump out water until the draw is used up
        if bin_count == 0:
            Water_Dumped = Flow_Rate * Time_First_Bin
            Model.loc[Bin_Start, 'Hot Water Draw Volume (gal)'] += Water_Dumped  #Add the volume within the first covered bin
            Water_Quantity -= Water_Dumped #keep track of water remaining
            bin_count += 1 #keep track of correct bin to put water in
        else:
            if Water_Quantity >= Flow_Rate * Timestep: #if there is enough water left to flow for more than a whole timestep bin
                Water_Dumped = Flow_Rate * Timestep
                Model.loc[Bin_Start + bin_count, 'Hot Water Draw Volume (gal)'] += Water_Dumped  #Add the volume to the next bin
            else:
                Water_Dumped = Water_Quantity
                Model.loc[Bin_Start + bin_count, 'Hot Water Draw Volume (gal)'] += Water_Dumped  #dump the remainder of the water into the final bin
            bin_count += 1 #keep track of correct bin to put water in
            Water_Quantity -= Water_Dumped #keep track of water remaining

    if vary_inlet_temp == True:
        This_Inlet_Temperature = Draw_Profile.loc[i, 'Mains Temperature (deg F)'] #get inlet water temperature from profile
        for i in range(bin_count):
            Model.loc[Bin_Start+i, 'Inlet Water Temperature (deg F)'] = This_Inlet_Temperature

#fill in remaining values for mains temperature:
if vary_inlet_temp == True:
    Model['Inlet Water Temperature (deg F)'] = Model['Inlet Water Temperature (deg F)'].replace(to_replace=0, method='ffill') #forward fill method - uses closed previous non-zero value
    Model['Inlet Water Temperature (deg F)'] = Model['Inlet Water Temperature (deg F)'].replace(to_replace=0, method='bfill') #backward fill method - uses closest subsequent non-zero value
else: #(vary_inlet_temp == False)
    Model['Inlet Water Temperature (deg F)'] = Temperature_Water_Inlet #Sets the inlet temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of value

Model['Ambient Temperature (deg F)'] = Temperature_Ambient #Sets the ambient temperature in the model equal to the value specified in INPUTS. This value could be replaced with a series of values

# Initializes a bunch of values at either 0 or initial temperature. They will be overwritten later as needed
Model['Tank Temperature (deg F)'] = 0
Model.loc[0, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
Model.loc[1, 'Tank Temperature (deg F)'] = Temperature_Tank_Initial
Model['Jacket Losses (Btu)'] = 0
Model['Energy Withdrawn (Btu)'] = 0
Model['Energy Added Backup (Btu)'] = 0
Model['Energy Added Heat Pump (Btu)'] = 0
Model['Energy Added Total (Btu)'] = 0
Model['COP Gas'] = 0
Model['Total Energy Change (Btu)'] = 0
Model['Timestep (min)'] = Timestep
Model['CO2 Production (lb)'] = 0
Model['Hour of Year (hr)'] = (Model['Time (min)']/60).astype(int)
Model['Electricity CO2 Multiplier (lb/kWh)'] = 0

#The following code simulates the performance of the gas HPWH
Model = GasHPWH.Model_GasHPWH_MixedTank(Model, Parameters, Regression_COP)

#%%--------------------------WRITE RESULTS TO FILE-----------------------------------------
Model.to_csv(Path_DrawProfile_Output, index = False) #Save the model to the declared file.

ET = time.time() #begin to time the script
print('script ran in {0} seconds'.format((ET - ST)))
