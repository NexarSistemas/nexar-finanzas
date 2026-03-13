
from .license_manager import validate_local_license
from .activation_gui import ActivationWindow
from .demo_state import LICENSE_MODE


def check_license():

    valid = validate_local_license()

    if not valid:

        window = ActivationWindow()
        window.run()

    return LICENSE_MODE
