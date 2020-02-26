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
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

ST = time.time() #begin to time the script


#%%--------------------------USER INPUTS------------------------------------------
Timestep = 5 #Timestep to use in the draw profile and simulation, in minutes

vary_inlet_temp = True # enter False to fix inlet water temperature constant, and True to take the inlet water temperature from the draw profile file (to make it vary by climate zone)

#%%---------------CONSTANT DECLARATIONS AND CALCULATIONS-----------------------

#Constants used in water-based calculations
SpecificHeat_Water = 0.998 #Btu/(lb_m-F) @ 80 deg F, http://www.engineeringtoolbox.com/water-properties-d_1508.html
Density_Water = 8.3176 #lb-m/gal @ 80 deg F, http://www.engineeringtoolbox.com/water-density-specific-weight-d_595.html

# used in --onefile exe
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


DrawProfile_app = tk.Tk()
DrawProfile_app.withdraw()
my_filetypes = [('all files', '.csv')]
Path_DrawProfile = filedialog.askopenfilename(parent=DrawProfile_app,
                                    initialdir=os.getcwd(),
                                    title="Please select the Draw Profile:",
                                    filetypes=my_filetypes)

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

# GUI: creates inputs window with default values
class Inputs:
    def __init__(self, master):
        self.master = master

        self.master.title('Gas HPWH Inputs') # GUI window label
        
        self.label_Temperature_Tank_Initial = tk.Label(master, text="Initial Tank Temperature (Deg F): ")
        self.label_Temperature_Tank_Initial.grid(row=1, column=1)
        self.entry_Temperature_Tank_Initial = tk.Entry(master)
        self.entry_Temperature_Tank_Initial.insert(0, 115) # Set defualt value
        self.entry_Temperature_Tank_Initial.grid(row=1, column=2)
        
        self.label_Temperature_Tank_Set = tk.Label(master, text="Tank Temperature Setpoint (Deg F): ")
        self.label_Temperature_Tank_Set.grid(row=2, column=1)
        self.entry_Temperature_Tank_Set = tk.Entry(master)
        self.entry_Temperature_Tank_Set.insert(0, 115)
        self.entry_Temperature_Tank_Set.grid(row=2, column=2)
        
        self.label_Temperature_Tank_Set_Deadband = tk.Label(master, text="Tank Temperature Deadband Setpoint (Deg F): ")
        self.label_Temperature_Tank_Set_Deadband.grid(row=3, column=1)
        self.entry_Temperature_Tank_Set_Deadband = tk.Entry(master)
        self.entry_Temperature_Tank_Set_Deadband.insert(0, 15)
        self.entry_Temperature_Tank_Set_Deadband.grid(row=3, column=2)
        
        self.label_Temperature_Water_Inlet = tk.Label(master, text="Inlet Water Temperature (Deg F): ")
        self.label_Temperature_Water_Inlet.grid(row=4, column=1)
        self.entry_Temperature_Water_Inlet = tk.Entry(master)
        self.entry_Temperature_Water_Inlet.insert(0, 40)
        self.entry_Temperature_Water_Inlet.grid(row=4, column=2)
        
        self.label_Temperature_Ambient = tk.Label(master, text="Ambient Temperature (Deg F): ")
        self.label_Temperature_Ambient.grid(row=5, column=1)
        self.entry_Temperature_Ambient = tk.Entry(master)
        self.entry_Temperature_Ambient.insert(0, 68)
        self.entry_Temperature_Ambient.grid(row=5, column=2)
        
        self.label_Volume_Tank = tk.Label(master, text="Tank Volume (gal): ")
        self.label_Volume_Tank.grid(row=6, column=1)
        self.entry_Volume_Tank = tk.Entry(master)
        self.entry_Volume_Tank.insert(0, 65)
        self.entry_Volume_Tank.grid(row=6, column=2)
        
        self.label_Coefficient_JacketLoss = tk.Label(master, text="JacketLoss Coefficient (W/K): ")
        self.label_Coefficient_JacketLoss.grid(row=7, column=1)
        self.entry_Coefficient_JacketLoss = tk.Entry(master)
        self.entry_Coefficient_JacketLoss.insert(0, 2.638)
        self.entry_Coefficient_JacketLoss.grid(row=7, column=2)
        
        self.label_Power_Backup = tk.Label(master, text="Backup Power (W): ")
        self.label_Power_Backup.grid(row=8, column=1)
        self.entry_Power_Backup = tk.Entry(master)
        self.entry_Power_Backup.insert(0, 1250)
        self.entry_Power_Backup.grid(row=8, column=2)
        
        self.label_Threshold_Activation_Backup = tk.Label(master, text="Backup Activation Threshold (Deg F): ")
        self.label_Threshold_Activation_Backup.grid(row=9, column=1)
        self.entry_Threshold_Activation_Backup = tk.Entry(master)
        self.entry_Threshold_Activation_Backup.insert(0,95)
        self.entry_Threshold_Activation_Backup.grid(row=9, column=2)
        
        self.label_Threshold_Deactivation_Backup = tk.Label(master, text="Backup Deactivation Threshold (Deg F): ")
        self.label_Threshold_Deactivation_Backup.grid(row=10, column=1)
        self.entry_Threshold_Deactivation_Backup = tk.Entry(master)
        self.entry_Threshold_Deactivation_Backup.insert(0,105)
        self.entry_Threshold_Deactivation_Backup.grid(row=10, column=2)
        
        self.label_FiringRate_HeatPump = tk.Label(master, text="Heat Consumed by Heat Pump/Firing rate (W): ")
        self.label_FiringRate_HeatPump.grid(row=11, column=1)
        self.entry_FiringRate_HeatPump = tk.Entry(master)
        self.entry_FiringRate_HeatPump.insert(0, 2930.72)
        self.entry_FiringRate_HeatPump.grid(row=11, column=2)
        
        self.label_ElectricityConsumption_Active = tk.Label(master, text="Active Electricity Consumption (W) ")
        self.label_ElectricityConsumption_Active.grid(row=12, column=1)
        self.entry_ElectricityConsumption_Active = tk.Entry(master)
        self.entry_ElectricityConsumption_Active.insert(0,110)
        self.entry_ElectricityConsumption_Active.grid(row=12, column=2)
        
        self.label_ElectricityConsumption_Idle= tk.Label(master, text="Idle Electricity Consumption (W): ")
        self.label_ElectricityConsumption_Idle.grid(row=13, column=1)
        self.entry_ElectricityConsumption_Idle = tk.Entry(master)
        self.entry_ElectricityConsumption_Idle.insert(0,5)
        self.entry_ElectricityConsumption_Idle.grid(row=13, column=2)
        
        self.label_NOx_Output= tk.Label(master, text="NOx Output (ng/J): ")
        self.label_NOx_Output.grid(row=14, column=1)
        self.entry_NOx_Output = tk.Entry(master)
        self.entry_NOx_Output.insert(0,10)
        self.entry_NOx_Output.grid(row=14, column=2)
        
        self.button_submit=tk.Button(master, text = "Submit", command=self.submit_inputs)
        self.button_submit.grid(row=15, column=2)
        
        
        #These inputs are a series of constants describing the conditions of the simulation. The constants describing the gas HPWH itself come from communications with Alex of GTI, and may
        #need to be updated if he sends new values
        # Set gas HPWH constant values
        self.Temperature_Tank_Initial = 115 #Deg F, initial temperature of water in the storage tank
        self.Temperature_Tank_Set = 115 #Deg F, set temperature of the HPWH
        self.Temperature_Tank_Set_Deadband = 15 #Deg F, deadband on the thermostat
        self.Temperature_Water_Inlet = 40 #Deg F, inlet water temperature in this simulation
        self.Temperature_Ambient = 68 #deg F, temperature of the ambient air, placeholder for now
        self.Volume_Tank = 65 #gal, volume of water held in the storage tank
        self.Coefficient_JacketLoss = 2.638 #W/K, based on e-mail from Alex Fridyland on 29 Mar 2019
        self.Power_Backup = 1250 #W, electricity consumption of the backup resistance elements
        self.Threshold_Activation_Backup = 95 #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
        self.Threshold_Deactivation_Backup = 105 #Deg F, sets the temperature when the backup element disengages after it has been engaged
        self.FiringRate_HeatPump = 2930.72 #W, heat consumed by the heat pump
        self.ElectricityConsumption_Active = 110 #W, electricity consumed by the fan when the heat pump is running
        self.ElectricityConsumption_Idle = 5 #W, electricity consumed by the HPWH when idle
        self.NOx_Output = 10 #ng/J, NOx production of the HP when active

        self.close_button = tk.Button(master, text="Next", command=master.quit)
        self.close_button.grid(row=17, column=2)

    def submit_inputs(self):
        self.Temperature_Tank_Initial = int(self.entry_Temperature_Tank_Initial.get())
        self.Temperature_Tank_Set = int(self.entry_Temperature_Tank_Set.get())
        self.Temperature_Tank_Set_Deadband = int(self.entry_Temperature_Tank_Set_Deadband.get())
        self.Temperature_Water_Inlet = int(self.entry_Temperature_Water_Inlet.get())
        self.Temperature_Ambient = int(self.entry_Temperature_Ambient.get())
        self.Volume_Tank = int(self.entry_Volume_Tank.get())
        self.Coefficient_JacketLoss = float(self.entry_Coefficient_JacketLoss.get())
        self.Power_Backup = int(self.entry_Power_Backup.get())
        self.Threshold_Activation_Backup = int(self.entry_Threshold_Activation_Backup.get())
        self.Threshold_Deactivation_Backup = int(self.entry_Threshold_Deactivation_Backup.get())
        self.FiringRate_HeatPump = float(self.entry_FiringRate_HeatPump.get())
        self.ElectricityConsumption_Active = float(self.entry_ElectricityConsumption_Active.get())
        self.ElectricityConsumption_Idle = float(self.entry_ElectricityConsumption_Idle.get())
        self.NOx_Output = int(self.entry_NOx_Output.get())
     
root_inputs = tk.Tk()
inputs = Inputs(root_inputs)
root_inputs.mainloop()


Temperature_Tank_Initial = inputs.Temperature_Tank_Initial #Deg F, initial temperature of water in the storage tank
Temperature_Tank_Set = inputs.Temperature_Tank_Set #Deg F, set temperature of the HPWH
Temperature_Tank_Set_Deadband = inputs.Temperature_Tank_Set_Deadband #Deg F, deadband on the thermostat
Temperature_Water_Inlet = inputs.Temperature_Water_Inlet #Deg F, inlet water temperature in this simulation
Temperature_Ambient = inputs.Temperature_Ambient #deg F, temperature of the ambient air, placeholder for now
Volume_Tank = inputs.Volume_Tank #gal, volume of water held in the storage tank
Coefficient_JacketLoss = inputs.Coefficient_JacketLoss #W/K, based on e-mail from Alex Fridyland on 29 Mar 2019
Power_Backup = inputs.Power_Backup #W, electricity consumption of the backup resistance elements
Threshold_Activation_Backup = inputs.Threshold_Activation_Backup #Deg F, backup element operates when tank temperature is below this threshold. Note that this operate at the same time as the heat pump
Threshold_Deactivation_Backup = inputs.Threshold_Deactivation_Backup #Deg F, sets the temperature when the backup element disengages after it has been engaged
FiringRate_HeatPump = inputs.FiringRate_HeatPump #W, heat consumed by the heat pump
ElectricityConsumption_Active = inputs.ElectricityConsumption_Active #W, electricity consumed by the fan when the heat pump is running
ElectricityConsumption_Idle = inputs.ElectricityConsumption_Idle #W, electricity consumed by the HPWH when idle
NOx_Output = inputs.NOx_Output #ng/J, NOx production of the HP when active


CO2_Output_Gas = 0.0053 #metric tons/therm, CO2 production when gas absorption heat pump is active
CO2_Output_Electricity = 0.212115 #ton/MWh, CO2 production when the HPWH consumes electricity. Default value is the average used in California
#Calculating the NOx production rate of the HPWH when HP is active
NOx_Production_Rate = NOx_Output * FiringRate_HeatPump * Seconds_In_Minute

#Calculating the CO2 production when the heat pump is active
CO2_Production_Rate_Gas = CO2_Output_Gas * FiringRate_HeatPump * W_To_BtuPerHour * (1/Minutes_In_Hour) * (1/Btu_In_Therm) * Pounds_In_MetricTon

#Calculating the CO2 produced per kWh of electricity consumed
CO_Production_Rate_Electricity = CO2_Output_Electricity * Pounds_In_Ton * kWh_In_MWh

#Converting quantities from SI units provided by Alex to (Incorrect, silly, obnoxious) IP units
Coefficient_JacketLoss = Coefficient_JacketLoss_WPerK * W_To_BtuPerHour / K_To_F_MagnitudeOnly #Converts Coefficient_JacketLoss from W/K to Btu/hr-F
Power_Backup = Power_Backup * W_To_BtuPerHour #Btu/hr
FiringRate_HeatPump = FiringRate_HeatPump * W_To_BtuPerHour #Btu/hr

#Calculating the thermal mass of the water in the storage tank
ThermalMass_Tank = Volume_Tank * Density_Water * SpecificHeat_Water

#Reading in the coefficients describing the COP of the gas HPWH as a function of the temperature of the water in the tank
#Coefficients_COP = np.genfromtxt('Coefficients' + os.sep + 'COP_Function_TReturn_F_6Nov2019.csv', delimiter=',') # Path edited for executable. np.genfromtxt to read in COP --onedir
#Coefficients_COP = np.genfromtxt(resource_path('Coefficients' + os.sep + 'COP_Function_TReturn_F_6Nov2019.csv'), delimiter=',') #--onefile

class COP_app:
    def __init__(self, master):
        self.master = master
        
        self.master.title('Coefficient of Performance')
        
        self.text = tk.Label(master, text="These coefficients, C1 and C2, describe the Coefficient of Performance (COP) of the heat pump.\n\nThe equation is as follows:\nCOP = (C1 x water temp) + C2\n")
        self.text.grid(row=1, columnspan=4)
        
        self.label_C1 = tk.Label(master, text="C1: ")
        self.label_C1.grid(row=2, column=1)
        self.entry_C1 = tk.Entry(master)
        self.entry_C1.insert(0,-0.0025)
        self.entry_C1.grid(row=2, column=2)
        
        self.label_C2 = tk.Label(master, text="C2: ")
        self.label_C2.grid(row=3, column=1)
        self.entry_C2 = tk.Entry(master)
        self.entry_C2.insert(0,2.0341)
        self.entry_C2.grid(row=3, column=2)   
        
        self.COP = np.zeros(2)
        
        self.button_submit=tk.Button(master, text = "Submit", command=self.submit_COP)
        self.button_submit.grid(row=5, columnspan=4)

        self.close_button = tk.Button(master, text="Run Simulation", command=master.quit)
        self.close_button.grid(row=6, columnspan=4)
        
        
    def submit_COP(self):
        self.COP[0] = self.entry_C1.get()
        self.COP[1] = self.entry_C2.get()
     
root_inputs.destroy() # Close the input window
root_COP = tk.Tk()
cop_app = COP_app(root_COP)
root_COP.mainloop()

Coefficients_COP= cop_app.COP
#Creates a 1 dimensional regression stating the COP of the gas heat pump as a function of the temperature of water in the tank
Regression_COP = np.poly1d(Coefficients_COP)

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
                CO_Production_Rate_Electricity] #12

#Close COP window
root_COP.destroy()

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

#The following code simulates the performance of the gas HPWH
Model = GasHPWH.Model_GasHPWH_MixedTank(Model, Parameters, Regression_COP)

#%%--------------------------WRITE RESULTS TO FILE-----------------------------------------

Path_DrawProfile_Output_Base_Path = 'Output'
Path_DrawProfile_Output_File_Name = Path_DrawProfile
Path_DrawProfile_Output = Path_DrawProfile_Output_Base_Path + os.sep + Path_DrawProfile_Output_File_Name
# Make output dir if it doesn't already exist:
if not os.path.exists('Output'):
    os.makedirs('Output')
Model.to_csv(Path_DrawProfile_Output, index = False) #Save the model to the declared file.

ET = time.time() #begin to time the script
print('script ran in {0} seconds'.format((ET - ST)))
