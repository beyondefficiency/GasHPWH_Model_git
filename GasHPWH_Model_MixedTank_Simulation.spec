# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['GasHPWH_Model_MixedTank_Simulation.py'],
             pathex=['C:\\Users\\aliu\\Desktop\\Github\\GasHPWH_Model_git'],
             binaries=[],
             datas=[('Coefficients/COP_Function_TReturn_F_6Nov2019.csv', './Coefficients'), 
			 ('Data/Draw_Profiles/Profile_Single_1BR_CFA=605_Weather=CA12_Setpoint=125.csv', './Data/Draw_Profiles')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='GasHPWH_Model_MixedTank_Simulation',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='GasHPWH_Model_MixedTank_Simulation')
