from setuptools import setup

APP = ['lan_house_manager.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': [],
    'includes': ['tkinter', 'json', 'datetime'],
    'plist': {
        'CFBundleName': 'LAN House Manager',
        'CFBundleDisplayName': 'LAN House Manager',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'LSUIElement': False,
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
