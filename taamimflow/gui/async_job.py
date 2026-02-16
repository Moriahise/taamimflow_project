"""Helper classes for running long-running tasks in a background thread.

This module defines a ``Job`` class and associated ``JobSignals`` to
facilitate asynchronous execution of time-consuming functions without
blocking the Qt event loop.  It relies on Qt's ``QRunnable`` and
signals/slots mechanism.  A consumer can submit a ``Job`` to the
global ``QThreadPool`` and connect to the ``result``, ``error`` and
``finished`` signals to update the UI when the task completes.

Example usage::

    from PyQt6.QtCore import QThreadPool
    from .async_job import Job

    def long_operation(x, y):
        # ... heavy computation or network call ...
        return x + y

    job = Job(long_operation, 2, 3)
    job.signals.result.connect(handle_result)
    job.signals.error.connect(handle_error)
    job.signals.finished.connect(cleanup)
    QThreadPool.globalInstance().start(job)

The above will run ``long_operation(2, 3)`` in a separate thread and
invoke the connected callbacks when done.

These helpers are intentionally lightweight and do not impose any
higher-level abstractions; they can be integrated into various parts
of the GUI code to provide responsive interfaces during network
requests or CPU-bound processing.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class JobSignals(QObject):
    """Defines the signals available from a running job.

    Instances of this class are owned by :class:`Job` objects.  It
    provides three Qt signals:

    ``result``
        Emitted with the result of the function when it completes successfully.

    ``error``
        Emitted with a string representation of the exception if the
        function raises.

    ``finished``
        Emitted when the job is finished, regardless of success or
        failure.  Useful for cleanup or UI state restoration.
    """

    #: Signal emitted with the return value of the job function.
    result = pyqtSignal(object)
    #: Signal emitted when an exception occurs, carrying the error message.
    error = pyqtSignal(str)
    #: Signal emitted when the job is finished.
    finished = pyqtSignal()


class Job(QRunnable):
    """Wraps a callable for execution in a separate thread.

    ``Job`` instances are intended to be submitted to a
    :class:`~PyQt6.QtCore.QThreadPool`.  They accept a function ``fn``
    along with positional and keyword arguments.  When run, the function
    is invoked and the result, error or finished signals are emitted as
    appropriate.

    :param fn: Callable to execute.
    :param args: Positional arguments to pass to ``fn``.
    :param kwargs: Keyword arguments to pass to ``fn``.
    """

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = JobSignals()

    @pyqtSlot()
    def run(self) -> None:
        """Execute the function and emit signals as appropriate."""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:
            # Propagate exceptions via the error signal; convert to string
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()