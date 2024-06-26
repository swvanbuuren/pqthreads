"""
Module for controlling of and communication between worker and GUI thread. It
provides a base class for controllers that control the communication between a
worker thread and the GUI thread.
"""

import sys
import weakref
from pqthreads.qt import QtCore, QtWidgets
from pqthreads import agents
from pqthreads import utils
from pqthreads import containers


class MissingReferenceError(Exception):
    """ Exception for missing references """


class WeakReferences:
    """ Class for holding weak references """
    def __init__(self):
        self.refs = {}

    def add(self, name, agent):
        """ Adds a new weak reference """
        self.refs[name] = weakref.proxy(agent)

    def get(self, name):
        """ Returns the weak reference """
        try:
            ref = self.refs[name]
        except KeyError as exc:
            raise KeyError(f'No weak reference found for {name}') from exc
        if not ref:
            raise MissingReferenceError(f'No weak reference set to {name}')
        return ref


worker_refs = WeakReferences()
gui_refs = WeakReferences()


class WorkerAgency(QtCore.QObject):
    """ Owns all worker agents """
    stopSignalwait = QtCore.Signal()
    workerErrorSignal = QtCore.Signal()

    def __init__(self, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.worker_agents = {}
        self.worker_containers = {}
        if worker_agents := kwargs.get('agents'):
            for name, agent in worker_agents.items():
                self.worker_agents[name] = agent

    def add_agent(self, name):
        """ Adds a new sender """
        self.worker_agents[name] = agents.WorkerAgent(name, parent=self)
        self.stopSignalwait.connect(self.worker_agents[name].stopSignalwait.emit)

    def agent(self, name):
        """ Returns the worker agent """
        return self.worker_agents[name]

    def add_container(self, name, item_class: containers.WorkerItem):
        """ Adds a new container, including a module wide weak reference """
        agent = self.agent(name)
        item_class = item_class.with_agent(agent)
        container = containers.WorkerItemContainer(item_class=item_class)
        self.worker_containers[name] = container
        worker_refs.add(name, container)


class FunctionWorker(QtCore.QObject):
    """ Worker thread that runs a user-supplied function """
    finished = QtCore.Signal()

    def __init__(self, function, agency, *args, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.function = function
        self.agency = agency
        self.args = args
        self.kwargs = kwargs
        self.result = None

    @QtCore.Slot()
    def run(self):
        """ Run the function with exception handling """
        try:
            self.result = self.function(*self.args, **self.kwargs)
        except BaseException: # pylint: disable=broad-except
            self.agency.workerErrorSignal.emit()
            raise
        finally:
            self.finished.emit()

    def get_result(self):
        """ Return the result """
        return self.result


class GUIAgency(QtCore.QObject):
    """ Controller class which coordinates all figure and axis objects """
    gui_agents = {}
    worker_agents = []

    @classmethod
    def add_agent(cls, name, item_class):
        """ Add GUI agent """
        container = containers.GUIItemContainer(item_class)
        cls.gui_agents[name] = agents.GUIAgent(name, container)
        gui_refs.add(name, container)
        cls.worker_agents.append(name)

    def __init__(self, worker, *args, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.application = self.get_application()
        self.result = None
        self.exception_raised = False
        self.raised_exception = None
        self.thread = QtCore.QThread(parent=self)
        self.worker_agency = WorkerAgency()
        self.worker = FunctionWorker(worker, self.worker_agency, *args, **kwargs)
        self.setup_worker()

    def kickoff(self):
        """ Kick off the worker thread """
        self.execute()

    @staticmethod
    def get_application():
        """ Returns the QApplication instance """
        if not QtWidgets.QApplication.instance():
            return QtWidgets.QApplication(sys.argv)
        return QtWidgets.QApplication.instance()

    def setup_worker(self):
        """ Setup worker thread """
        # add worker agents
        for worker_agent in self.worker_agents:
            self.worker_agency.add_agent(worker_agent)
        self.worker.moveToThread(self.thread)
        self.worker_agency.moveToThread(self.thread)
        # connect agents
        for name, agent in self.gui_agents.items():
            self.worker_agency.agent(name).connect_agent(agent)
        self.worker_agency.workerErrorSignal.connect(self.application.closeAllWindows)
        # connect other signals/slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.stop_thread)

    def excepthook(self, exc_type, exc_value, exc_tb):
        """ Catch any exception and print it """
        self.raised_exception = (exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        self.worker_agency.stopSignalwait.emit()

    def execute(self):
        """ Create QApplication, start worker thread and the main event loop """
        self.thread.start()
        try:
            sys.excepthook = self.excepthook
            utils.compat_exec(self.application)
        finally:
            self.wait_for_thread()
            if self.raised_exception:
                exc_type, exc_value, exc_tb = self.raised_exception
                raise exc_type(exc_value).with_traceback(exc_tb)
            self.application.exit()

    @QtCore.Slot()
    def stop_thread(self):
        """ Stop the worker thread """
        self.result = self.worker.get_result()
        self.thread.quit()
        self.thread.wait()
        self.exit_windowless_application()

    @QtCore.Slot()
    def exit_windowless_application(self):
        """ Exit the application if now windows are open """
        if not self.application.topLevelWidgets():
            self.application.exit()

    def wait_for_thread(self):
        """ Wait for the worker thread to finish """
        while True:
            try:
                if not self.thread.isRunning():
                    break
            except RuntimeError:
                break
            self.application.processEvents()
