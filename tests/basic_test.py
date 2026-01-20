""" Test the pqthreads container module """

import pytest
from pqthreads.examples import window
from pqthreads.examples import worker
from pqthreads.config import params
from pqthreads.qt import QtCore, QtWidgets


def test_empty():
    """ Standard test with any used functionalities, should end without errors """

    @worker.decorator_example
    def main():
        """ Helper function """

    main()


def test_basic():
    """ Basic functionality check, should not raise any errors """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.close()

    main()


def test_method():
    """ Test return value of method call from the worker thread """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        title = fig.change_title('Hello from worker')
        fig.close()
        return title

    result = main()
    assert result == 'Figure 1: Hello from worker'

def test_attribute():
    """ Test attribute property """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.title = 'Hello from worker'
        title = fig.title
        fig.close()
        return title

    result = main()
    assert result == 'Figure 1: Hello from worker'


def test_gui_exception():
    """ Test exception in GUI thread """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.raise_exception()
        fig.close()

    with pytest.raises(window.FigureWindowException):
        main()


def test_worker_exception():
    """ Test exception in worker thread """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.raise_worker_exception()
        fig.close()

    with pytest.raises(worker.FigureWorkerException):
        main()


def test_multiple_figure_closure():
    """ Test closure of multiple figures """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig1 = worker.figure()
        fig2 = worker.figure()
        fig3 = worker.figure()
        fig4 = worker.figure()
        fig1.close()
        fig2.close()
        fig3.close()
        fig4.close()

    try:
        main()
    except IndexError:
        pytest.fail("Unexpected IndexError")


def test_multiple_agent_types():
    """ Test functionality of multiple agent types """

    @worker.decorator_example
    def main():
        """ Helper function """
        fig = worker.figure()
        graph = worker.graph()
        result = graph.test_method()
        fig.close()
        graph.close()
        return result

    result = main()
    assert result == 'Test successful'


def test_decorator_keyword_argument():
    """ Test functionality of single decorator keyword argument """

    @worker.decorator_example(keyword_argument='test')
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.close()

    main()
    assert worker.global_kwargs['keyword_argument'] == 'test'


def test_multiple_decorator_keyword_arguments():
    """ Test functionality of multiple decorator keyword arguments """

    @worker.decorator_example(first_kwarg='first_arg', second_kw='second_arg')
    def main():
        """ Helper function """
        fig = worker.figure()
        fig.close()

    main()
    assert worker.global_kwargs['first_kwarg'] == 'first_arg'
    assert worker.global_kwargs['second_kw'] == 'second_arg'


def test_set_application_attribute():
    """ Test setting an application attribute via configuration """

    params.add_application_attribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    try:
        @worker.decorator_example
        def main():
            """ Helper function """
            fig = worker.figure()
            fig.close()

        main()

        if app := QtWidgets.QApplication.instance():
            assert app.testAttribute(QtCore.Qt.ApplicationAttribute.AA_ShareOpenGLContexts) is True
        else:
            pytest.fail("QApplication instance was not created")
    finally:
        params.application_attributes.clear()
