"""
Module for controlling of and communication between worker and GUI thread. It
provides a base class for controllers that control the communication between a
worker thread and the GUI thread.
"""

import sys
from pqthreads.qt import QtCore, QtWidgets
from pqthreads import agents
from pqthreads import utils
from pqthreads import containers
from pqthreads import refs
from pqthreads.config import params


class WorkerAgency(QtCore.QObject):
    """ Owns all worker agents """
    workerErrorSignal = QtCore.Signal(tuple)

    def __init__(self, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.worker_agents = {}
        self.worker_containers = {}
        if worker_agents := kwargs.get('agents'):
            for name, agent in worker_agents.items():
                self.worker_agents[name] = agent
        self.raised_exception = None

    def add_agent(self, name):
        """ Adds a new sender """
        self.worker_agents[name] = agents.WorkerAgent(name, parent=self)

    def agent(self, name):
        """ Returns the worker agent """
        return self.worker_agents[name]

    def add_container(self, name, item_class: containers.WorkerItem):
        """ Adds a new container, including a module wide weak reference """
        agent = self.agent(name)
        item_class = item_class.with_agent(agent)
        container = containers.WorkerItemContainer(item_class=item_class)
        self.worker_containers[name] = container
        refs.worker.add(name, container)

    def stop_signal_wait(self):
        """ Stop signal wait """
        for agent in self.worker_agents.values():
            agent.stopSignalwait.emit()


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
        except BaseException as err: # pylint: disable=broad-except
            raised_exception = (type(err), err, err.__traceback__)
            self.agency.workerErrorSignal.emit(raised_exception)
        finally:
            self.finished.emit()

    def get_result(self):
        """ Return the result """
        return self.result


class GUIAgency(QtCore.QObject): # pylint: disable=too-many-instance-attributes
    """ Controller class which coordinates all figure and axis objects """
    gui_agents_classes = {}
    worker_agents = []

    @classmethod
    def add_agent(cls, name, item_class):
        """ Add GUI agent """
        cls.gui_agents_classes[name] = item_class
        cls.worker_agents.append(name)

    def __init__(self, worker, *args, **kwargs):
        super().__init__(kwargs.pop('parent', None))
        self.application = self.get_application()
        self.gui_agents = {}
        self.gui_containers = {}
        self.result = None
        self.raised_exception = None
        self.thread = QtCore.QThread(parent=self)
        self.worker_agency = WorkerAgency()
        self.worker = FunctionWorker(worker, self.worker_agency, *args, **kwargs)
        self.setup_agents()
        self.setup_worker()

    @staticmethod
    def get_application():
        """ Returns the QApplication instance """
        for attribute in params.application_attributes:
            QtWidgets.QApplication.setAttribute(attribute.atype, attribute.on)
        if not QtWidgets.QApplication.instance():
            return QtWidgets.QApplication(sys.argv)
        return QtWidgets.QApplication.instance()

    def setup_agents(self):
        """ Setup GUI agents """
        for name, item_class in self.gui_agents_classes.items():
            self.gui_containers[name] = containers.GUIItemContainer(item_class, parent=self)
            self.gui_agents[name] = agents.GUIAgent(name, self.gui_containers[name], parent=self)
            refs.gui.add(name, self.gui_containers[name])

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
            agent.connect_agent(self.worker_agency.agent(name))
        self.worker_agency.workerErrorSignal.connect(self.worker_exception_raised)
        # connect other signals/slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.stop_thread)

    def excepthook(self, exc_type, exc_value, exc_tb):
        """ Catch any exception and print it """
        self.raised_exception = (exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        self.worker_agency.stop_signal_wait()

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

    @QtCore.Slot()
    def worker_exception_raised(self, worker_exception):
        """ Make sure the GUI threads stops, by closing all open windows and
        register the caught exception """
        self.application.closeAllWindows()
        self.raised_exception = worker_exception
        sys.__excepthook__(*worker_exception)
