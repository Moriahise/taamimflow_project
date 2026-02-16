"""Graphical user interface for Ta'amimFlow.

This subpackage contains all PyQt6 widgets, dialogs and windows used
by the application.  The GUI is designed to be modular so that
individual components can be replaced or extended without affecting
the rest of the system.  Each widget lives in its own module with
clear responsibilities.

Note that the GUI depends on the ``PyQt6`` package, which is listed
in ``requirements.txt``.  If you are developing on a headless
environment, you may need to install additional platform plugins or
mock certain Qt classes to run tests.
"""