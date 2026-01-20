"""Configuration for the pqthreads"""

from dataclasses import dataclass, field
from pqthreads.qt import QtCore

@dataclass
class Attribute:
    """Wrapper for Qt Application Attributes"""

    atype: QtCore.Qt.ApplicationAttribute
    on: bool = True


@dataclass
class Parameters:
    """Configuration parameters for pqthreads"""

    signal_slot_timeout: int = 1_000
    application_attributes: list[Attribute] = field(default_factory=list)

    def set_application_attribute(
            self,
            attribute: QtCore.Qt.ApplicationAttribute,
            on: bool = True) -> None:
        """Add an application attribute to be set on QApplication creation"""
        self.application_attributes.append(Attribute(attribute, on))


params = Parameters()
