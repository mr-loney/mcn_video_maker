# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['ResToolMain.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cache', 'cache'),
        ('tiktok-tools', 'tiktok-tools'),
        ('chrome_driver', 'chrome_driver'),
        ('resproject', 'resproject'),
        ('models', 'models'),
        ('loras', 'loras'),
        ('workflows', 'workflows'),
        ('vid_workflows', 'vid_workflows'),
        ('audiolist', 'audiolist'),
        ('last_folder_path.json', '.'),
        ('checkweb.json', '.'),
        ('key.json', '.'),
        ('folder_icon.png', '.'),
        ('audio_icon.png', '.'),
        ('/opt/homebrew/bin/ffmpeg', 'ffmpeg'),
        ('/opt/homebrew/bin/ffprobe', 'ffprobe'),
        ('/opt/homebrew/bin/ffplay', 'ffplay'),
        ('/opt/homebrew/bin/aria2c', 'aria2c')
    ],
    hiddenimports=[
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.common',
        'undetected-chromedriver',
        'openpyxl',
        'torch',
        'torchvision',
        'torchaudio',
        'typing_extensions',
        'numpy',
        'opencv-python',
        'pillow',
        'requests',
        'protobuf',
        'betterproto',
        'setproctitle',
        'pyperclip',
        'opencv-python',
        'cv2'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ResToolMain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ResToolMain',
)