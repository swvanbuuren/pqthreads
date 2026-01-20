"""Configuration for the pqthreads"""

from dataclasses import dataclass, field
from pqthreads.qt import QtCore


@dataclass
class Parameters:
    """Configuration parameters for pqthreads"""

    signal_slot_timeout: int = 1_000
    application_attributes: list[QtCore.Qt.ApplicationAttribute] = field(default_factory=list)

    def add_application_attribute(self, attribute: QtCore.Qt.ApplicationAttribute) -> None:
        """Add an application attribute to be set on QApplication creation"""
        self.application_attributes.append(attribute)


params = Parameters()
