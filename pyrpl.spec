# -*- mode: python -*-

block_cipher = None


import os
import sys

# needed to pack the qt libraries along with the exe
#try:
#    qt_plugin_path = os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"]
#except:
#    qt_plugin_path = ''
#if qt_plugin_path == '':
#    try:
#        path, _ = os.path.split(sys.executable).rstrip('bin')
#        if os.path.exists(os.path.join(path, 'Library')):
#            path = os.path.join(path, 'Library')  # needed on windows systems
#        qt_plugin_path = os.path.join(path, 'plugins', 'platforms')
#    except:
#        pass


a = Analysis(['pyrpl/__main__.py'],
             pathex=['.'],
             binaries=[], # (os.path.join(qt_plugin_path, '*'), 'plugins')],
             datas=[('pyrpl/fpga/red_pitaya.bin', 'pyrpl/fpga'),
                    ('pyrpl/monitor_server/monitor_server*',
                     'pyrpl/monitor_server')],
             hiddenimports=['scipy._lib.messagestream', '_sysconfigdata_m_darwin_'],
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
          upx=False,
          console=True )

