
LICENSE_MODE = "DEMO"
LICENSE_DATA = None


def set_full(data):
    global LICENSE_MODE, LICENSE_DATA
    LICENSE_MODE = "FULL"
    LICENSE_DATA = data


def set_demo():
    global LICENSE_MODE, LICENSE_DATA
    LICENSE_MODE = "DEMO"
    LICENSE_DATA = None
