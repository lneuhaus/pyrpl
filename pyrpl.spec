# -*- mode: python -*-

block_cipher = None


a = Analysis(['pyrpl/__main__.py'],
             pathex=['.'],
             binaries=[],
             datas=[('pyrpl/fpga/red_pitaya.bin', 'pyrpl/fpga'),
                    ('pyrpl/monitor_server/monitor_server*',
                     'pyrpl/monitor_server')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='pyrpl',
          debug=False,
          strip=False,
          upx=True,
          console=True )
