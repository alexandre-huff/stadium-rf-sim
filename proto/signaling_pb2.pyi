from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OfhMessage(_message.Message):
    __slots__ = ("registration_request", "registration_response", "deregistration_request", "deregistration_response", "metrics_request", "metrics_response", "handover_request", "handover_response", "tx_reference_level_request", "tx_reference_level_response", "ru_setup_request", "ru_setup_response", "ru_teardown_request", "ru_teardown_response")
    REGISTRATION_REQUEST_FIELD_NUMBER: _ClassVar[int]
    REGISTRATION_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    DEREGISTRATION_REQUEST_FIELD_NUMBER: _ClassVar[int]
    DEREGISTRATION_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    METRICS_REQUEST_FIELD_NUMBER: _ClassVar[int]
    METRICS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    HANDOVER_REQUEST_FIELD_NUMBER: _ClassVar[int]
    HANDOVER_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    TX_REFERENCE_LEVEL_REQUEST_FIELD_NUMBER: _ClassVar[int]
    TX_REFERENCE_LEVEL_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    RU_SETUP_REQUEST_FIELD_NUMBER: _ClassVar[int]
    RU_SETUP_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    RU_TEARDOWN_REQUEST_FIELD_NUMBER: _ClassVar[int]
    RU_TEARDOWN_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    registration_request: UeRegistrationRequestMessage
    registration_response: UeRegistrationResponseMessage
    deregistration_request: UeDeregistrationRequestMessage
    deregistration_response: UeDeregistrationResponseMessage
    metrics_request: UeMetricsRequestMessage
    metrics_response: UeMetricsResponseMessage
    handover_request: HandoverRequestMessage
    handover_response: HandoverResponseMessage
    tx_reference_level_request: TxReferenceLevelRequestMessage
    tx_reference_level_response: TxReferenceLevelResponseMessage
    ru_setup_request: RadioUnitSetupRequestMessage
    ru_setup_response: RadioUnitSetupResponseMessage
    ru_teardown_request: RadioUnitTearDownRequestMessage
    ru_teardown_response: RadioUnitTearDownResponseMessage
    def __init__(self, registration_request: _Optional[_Union[UeRegistrationRequestMessage, _Mapping]] = ..., registration_response: _Optional[_Union[UeRegistrationResponseMessage, _Mapping]] = ..., deregistration_request: _Optional[_Union[UeDeregistrationRequestMessage, _Mapping]] = ..., deregistration_response: _Optional[_Union[UeDeregistrationResponseMessage, _Mapping]] = ..., metrics_request: _Optional[_Union[UeMetricsRequestMessage, _Mapping]] = ..., metrics_response: _Optional[_Union[UeMetricsResponseMessage, _Mapping]] = ..., handover_request: _Optional[_Union[HandoverRequestMessage, _Mapping]] = ..., handover_response: _Optional[_Union[HandoverResponseMessage, _Mapping]] = ..., tx_reference_level_request: _Optional[_Union[TxReferenceLevelRequestMessage, _Mapping]] = ..., tx_reference_level_response: _Optional[_Union[TxReferenceLevelResponseMessage, _Mapping]] = ..., ru_setup_request: _Optional[_Union[RadioUnitSetupRequestMessage, _Mapping]] = ..., ru_setup_response: _Optional[_Union[RadioUnitSetupResponseMessage, _Mapping]] = ..., ru_teardown_request: _Optional[_Union[RadioUnitTearDownRequestMessage, _Mapping]] = ..., ru_teardown_response: _Optional[_Union[RadioUnitTearDownResponseMessage, _Mapping]] = ...) -> None: ...

class RadioUnitSetupRequestMessage(_message.Message):
    __slots__ = ("cells",)
    CELLS_FIELD_NUMBER: _ClassVar[int]
    cells: _containers.RepeatedCompositeFieldContainer[Cell]
    def __init__(self, cells: _Optional[_Iterable[_Union[Cell, _Mapping]]] = ...) -> None: ...

class RadioUnitSetupResponseMessage(_message.Message):
    __slots__ = ("status", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: bool
    error: str
    def __init__(self, status: bool = ..., error: _Optional[str] = ...) -> None: ...

class RadioUnitTearDownRequestMessage(_message.Message):
    __slots__ = ("cells",)
    CELLS_FIELD_NUMBER: _ClassVar[int]
    cells: _containers.RepeatedCompositeFieldContainer[Cell]
    def __init__(self, cells: _Optional[_Iterable[_Union[Cell, _Mapping]]] = ...) -> None: ...

class RadioUnitTearDownResponseMessage(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: bool
    def __init__(self, status: bool = ...) -> None: ...

class UeRegistrationRequestMessage(_message.Message):
    __slots__ = ("ue_metrics",)
    UE_METRICS_FIELD_NUMBER: _ClassVar[int]
    ue_metrics: _containers.RepeatedCompositeFieldContainer[UeMetrics]
    def __init__(self, ue_metrics: _Optional[_Iterable[_Union[UeMetrics, _Mapping]]] = ...) -> None: ...

class UeRegistrationResponseMessage(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: bool
    def __init__(self, status: bool = ...) -> None: ...

class UeDeregistrationRequestMessage(_message.Message):
    __slots__ = ("ues",)
    UES_FIELD_NUMBER: _ClassVar[int]
    ues: _containers.RepeatedCompositeFieldContainer[UeDeregistration]
    def __init__(self, ues: _Optional[_Iterable[_Union[UeDeregistration, _Mapping]]] = ...) -> None: ...

class UeDeregistrationResponseMessage(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: bool
    def __init__(self, status: bool = ...) -> None: ...

class UeMetricsRequestMessage(_message.Message):
    __slots__ = ("ue_metrics",)
    UE_METRICS_FIELD_NUMBER: _ClassVar[int]
    ue_metrics: _containers.RepeatedCompositeFieldContainer[UeMetrics]
    def __init__(self, ue_metrics: _Optional[_Iterable[_Union[UeMetrics, _Mapping]]] = ...) -> None: ...

class UeMetricsResponseMessage(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: bool
    def __init__(self, status: bool = ...) -> None: ...

class HandoverRequestMessage(_message.Message):
    __slots__ = ("ue", "target_cell")
    UE_FIELD_NUMBER: _ClassVar[int]
    TARGET_CELL_FIELD_NUMBER: _ClassVar[int]
    ue: UE
    target_cell: Cell
    def __init__(self, ue: _Optional[_Union[UE, _Mapping]] = ..., target_cell: _Optional[_Union[Cell, _Mapping]] = ...) -> None: ...

class HandoverResponseMessage(_message.Message):
    __slots__ = ("ue", "target_cell", "status", "error")
    UE_FIELD_NUMBER: _ClassVar[int]
    TARGET_CELL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ue: UE
    target_cell: Cell
    status: bool
    error: str
    def __init__(self, ue: _Optional[_Union[UE, _Mapping]] = ..., target_cell: _Optional[_Union[Cell, _Mapping]] = ..., status: bool = ..., error: _Optional[str] = ...) -> None: ...

class TxReferenceLevelRequestMessage(_message.Message):
    __slots__ = ("cell",)
    CELL_FIELD_NUMBER: _ClassVar[int]
    cell: Cell
    def __init__(self, cell: _Optional[_Union[Cell, _Mapping]] = ...) -> None: ...

class TxReferenceLevelResponseMessage(_message.Message):
    __slots__ = ("cell", "status", "error")
    CELL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    cell: Cell
    status: bool
    error: str
    def __init__(self, cell: _Optional[_Union[Cell, _Mapping]] = ..., status: bool = ..., error: _Optional[str] = ...) -> None: ...

class UeDeregistration(_message.Message):
    __slots__ = ("ue", "cell")
    UE_FIELD_NUMBER: _ClassVar[int]
    CELL_FIELD_NUMBER: _ClassVar[int]
    ue: UE
    cell: Cell
    def __init__(self, ue: _Optional[_Union[UE, _Mapping]] = ..., cell: _Optional[_Union[Cell, _Mapping]] = ...) -> None: ...

class UeMetrics(_message.Message):
    __slots__ = ("ue", "primary_cell", "neighbor_cells")
    UE_FIELD_NUMBER: _ClassVar[int]
    PRIMARY_CELL_FIELD_NUMBER: _ClassVar[int]
    NEIGHBOR_CELLS_FIELD_NUMBER: _ClassVar[int]
    ue: UE
    primary_cell: CellMetrics
    neighbor_cells: _containers.RepeatedCompositeFieldContainer[CellMetrics]
    def __init__(self, ue: _Optional[_Union[UE, _Mapping]] = ..., primary_cell: _Optional[_Union[CellMetrics, _Mapping]] = ..., neighbor_cells: _Optional[_Iterable[_Union[CellMetrics, _Mapping]]] = ...) -> None: ...

class Metrics(_message.Message):
    __slots__ = ("rsrp", "rsrq", "sinr")
    RSRP_FIELD_NUMBER: _ClassVar[int]
    RSRQ_FIELD_NUMBER: _ClassVar[int]
    SINR_FIELD_NUMBER: _ClassVar[int]
    rsrp: float
    rsrq: float
    sinr: float
    def __init__(self, rsrp: _Optional[float] = ..., rsrq: _Optional[float] = ..., sinr: _Optional[float] = ...) -> None: ...

class CellMetrics(_message.Message):
    __slots__ = ("cell", "metrics")
    CELL_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    cell: Cell
    metrics: Metrics
    def __init__(self, cell: _Optional[_Union[Cell, _Mapping]] = ..., metrics: _Optional[_Union[Metrics, _Mapping]] = ...) -> None: ...

class Cell(_message.Message):
    __slots__ = ("pci", "gain")
    PCI_FIELD_NUMBER: _ClassVar[int]
    GAIN_FIELD_NUMBER: _ClassVar[int]
    pci: int
    gain: float
    def __init__(self, pci: _Optional[int] = ..., gain: _Optional[float] = ...) -> None: ...

class UE(_message.Message):
    __slots__ = ("imsi",)
    IMSI_FIELD_NUMBER: _ClassVar[int]
    imsi: str
    def __init__(self, imsi: _Optional[str] = ...) -> None: ...
