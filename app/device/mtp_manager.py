"""
mtp_manager.py
Windows Portable Device (WPD) COM API wrapper using comtypes.

Provides Python classes to:
  - Enumerate connected Android/MTP devices
  - Navigate folder/file hierarchy on device
  - Stream files from device to PC

No third-party MTP library required – uses Windows built-in WPD COM API directly.
"""

import ctypes
import ctypes.wintypes
import logging
import datetime
import io
import os
from dataclasses import dataclass, field
from typing import Optional, Iterator, List

logger = logging.getLogger(__name__)

# ── Guard: Windows-only ───────────────────────────────────────────────────────
import sys
if sys.platform != "win32":
    raise ImportError("mtp_manager requires Windows.")

# ── Import comtypes ───────────────────────────────────────────────────────────
try:
    import comtypes
    import comtypes.client
    from comtypes import GUID, IUnknown, HRESULT, COMMETHOD, POINTER
    _COMTYPES_AVAILABLE = True
except ImportError:
    _COMTYPES_AVAILABLE = False
    logger.error("comtypes not installed. MTP device access unavailable.")

# ── ctypes helpers ────────────────────────────────────────────────────────────
DWORD   = ctypes.c_ulong
ULONG   = ctypes.c_ulong
USHORT  = ctypes.c_ushort
LPWSTR  = ctypes.c_wchar_p
ULONGLONG = ctypes.c_ulonglong

# ── WPD CLSIDs / IIDs ────────────────────────────────────────────────────────
CLSID_PortableDeviceManager     = "{0AF10CEC-2ECD-4B92-9581-34F6AE0637F3}"
CLSID_PortableDeviceValues      = "{0C15D503-D017-47CE-9016-7B3F978721CC}"
CLSID_PortableDeviceKeyCollection = "{DE2D022D-2480-43BE-97F0-D1FA2CF98F4F}"

IID_IPortableDeviceManager      = "{A1567595-4C2F-4574-A6FA-ECEF917B9A40}"
IID_IPortableDevice             = "{625E2DF8-6392-4CF0-9AD1-3CFA5F17775C}"
IID_IPortableDeviceContent      = "{6A96ED84-7C73-4480-9938-BF5AF477D426}"
IID_IPortableDeviceProperties   = "{7F6D695C-03DF-4439-A809-59266BEEE3A6}"
IID_IPortableDeviceResources    = "{FD8878AC-D841-4D17-891C-E6829CDB6934}"
IID_IPortableDeviceValues       = "{6848F6F2-3155-4F86-B6F5-263EEEAB3143}"
IID_IPortableDeviceKeyCollection= "{DADA2357-E0AD-492E-98DB-DD61C53BA353}"
IID_IEnumPortableDeviceObjectIDs= "{10ECE955-CF41-4728-BFA0-41EEDF1BBF19}"
IID_IPortableDevicePropVariantCollection = "{89B2E422-4F1B-4316-BCEF-A44AFEA83EB3}"
IID_IStream                     = "{0000000C-0000-0000-C000-000000000046}"

# ── WPD Property Keys ─────────────────────────────────────────────────────────
_OBJECT_PROP_FMTID = "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}"
_CLIENT_INFO_FMTID = "{204D9F0C-2292-4080-9F42-40664E70F859}"

WPD_OBJECT_PARENT_ID            = (_OBJECT_PROP_FMTID, 3)
WPD_OBJECT_NAME                 = (_OBJECT_PROP_FMTID, 4)
WPD_OBJECT_CONTENT_TYPE         = (_OBJECT_PROP_FMTID, 7)
WPD_OBJECT_SIZE                 = (_OBJECT_PROP_FMTID, 11)
WPD_OBJECT_ORIGINAL_FILE_NAME   = (_OBJECT_PROP_FMTID, 12)
WPD_OBJECT_DATE_CREATED         = (_OBJECT_PROP_FMTID, 18)
WPD_OBJECT_DATE_MODIFIED        = (_OBJECT_PROP_FMTID, 19)
WPD_OBJECT_PERSISTENT_UNIQUE_ID = (_OBJECT_PROP_FMTID, 5)

WPD_CLIENT_NAME                 = (_CLIENT_INFO_FMTID, 2)
WPD_CLIENT_MAJOR_VERSION        = (_CLIENT_INFO_FMTID, 3)
WPD_CLIENT_MINOR_VERSION        = (_CLIENT_INFO_FMTID, 4)
WPD_CLIENT_REVISION             = (_CLIENT_INFO_FMTID, 5)

# WPD Content Type GUIDs
WPD_CONTENT_TYPE_FOLDER         = "{27E2E392-A111-48E0-AB0C-E17705A05F85}"
WPD_CONTENT_TYPE_IMAGE          = "{EF2107D5-A52A-4243-A26B-62D4176D7603}"
WPD_CONTENT_TYPE_VIDEO          = "{9261B03C-3D78-4519-85E3-02C5E1F50BB9}"
WPD_CONTENT_TYPE_AUDIO          = "{4AD2C85E-5E2D-45E5-8864-4F229E3C6CF0}"
WPD_CONTENT_TYPE_UNSPECIFIED    = "{28D8D31E-249C-454E-AABC-34883168E634}"
WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT = "{99ED0160-17FF-4C44-9D98-1D7A6F941921}"

WPD_RESOURCE_DEFAULT_FMTID      = "{E81E79BE-34F0-41BF-B53F-F1A06AE87842}"

STGM_READ = 0x00000000
WPD_DEVICE_OBJECT_ID = "DEVICE"


# ── PROPVARIANT ───────────────────────────────────────────────────────────────
VT_EMPTY   = 0
VT_BOOL    = 11
VT_DATE    = 7
VT_LPWSTR  = 31
VT_UI4     = 19
VT_UI8     = 21
VT_UINT    = 23
VT_CLSID   = 72
VT_UNKNOWN = 13
VT_ERROR   = 10


class _PV_UNION(ctypes.Union):
    _fields_ = [
        ("llVal",   ctypes.c_longlong),
        ("lVal",    ctypes.c_long),
        ("ulVal",   ctypes.c_ulong),
        ("uhVal",   ctypes.c_ulonglong),
        ("boolVal", ctypes.c_short),
        ("dblVal",  ctypes.c_double),
        ("pwszVal", ctypes.c_void_p),   # LPWSTR stored as raw ptr
        ("puuid",   ctypes.c_void_p),   # GUID*
        ("punkVal", ctypes.c_void_p),   # IUnknown*
    ]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt",        USHORT),
        ("reserved1", USHORT),
        ("reserved2", USHORT),
        ("reserved3", USHORT),
        ("_val",      _PV_UNION),
    ]

    @property
    def value(self):
        vt = self.vt
        if vt == VT_LPWSTR:
            ptr = self._val.pwszVal
            if ptr:
                return ctypes.wstring_at(ptr)
            return None
        elif vt == VT_UI8 or vt == VT_UINT:
            return self._val.uhVal
        elif vt == VT_UI4:
            return self._val.ulVal
        elif vt == VT_DATE:
            # OLE Automation date: float days since 1899-12-30
            days = self._val.dblVal
            base = datetime.datetime(1899, 12, 30)
            try:
                return base + datetime.timedelta(days=days)
            except Exception:
                return None
        elif vt == VT_BOOL:
            return bool(self._val.boolVal)
        elif vt == VT_CLSID:
            if self._val.puuid:
                guid = GUID()
                ctypes.memmove(ctypes.byref(guid), self._val.puuid, ctypes.sizeof(GUID))
                return str(guid)
            return None
        elif vt == VT_EMPTY or vt == VT_ERROR:
            return None
        return None


# ── PROPERTYKEY ───────────────────────────────────────────────────────────────
class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", DWORD)]

    @classmethod
    def from_tuple(cls, tup: tuple) -> "PROPERTYKEY":
        pk = cls()
        pk.fmtid = GUID(tup[0])
        pk.pid   = tup[1]
        return pk


# ── COM Interface Definitions ─────────────────────────────────────────────────
if _COMTYPES_AVAILABLE:

    class IPortableDeviceManager(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceManager)
        _methods_ = [
            COMMETHOD([], HRESULT, "GetDevices",
                (["in"], POINTER(LPWSTR), "pPnPDeviceIDs"),
                (["in"], POINTER(DWORD), "pcPnPDeviceIDs")),
            COMMETHOD([], HRESULT, "RefreshDeviceList"),
            COMMETHOD([], HRESULT, "GetDeviceFriendlyName",
                (["in"], LPWSTR, "pszPnPDeviceID"),
                (["in", "out"], POINTER(LPWSTR), "pDeviceFriendlyName"),
                (["in", "out"], POINTER(DWORD), "pcchDeviceFriendlyName")),
            COMMETHOD([], HRESULT, "GetDeviceDescription",
                (["in"], LPWSTR, "pszPnPDeviceID"),
                (["in", "out"], POINTER(LPWSTR), "pDeviceDescription"),
                (["in", "out"], POINTER(DWORD), "pcchDeviceDescription")),
            COMMETHOD([], HRESULT, "GetDeviceManufacturer",
                (["in"], LPWSTR, "pszPnPDeviceID"),
                (["in", "out"], POINTER(LPWSTR), "pDeviceManufacturer"),
                (["in", "out"], POINTER(DWORD), "pcchDeviceManufacturer")),
            COMMETHOD([], HRESULT, "_GetDeviceProperty"),
            COMMETHOD([], HRESULT, "_GetPrivateDevices"),
        ]

    class IPortableDeviceValues(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceValues)
        _methods_ = [
            COMMETHOD([], HRESULT, "SetUnsignedIntegerValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["in"], DWORD, "dwValue")),
            COMMETHOD([], HRESULT, "GetUnsignedIntegerValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["out"], POINTER(DWORD), "pdwValue")),
            COMMETHOD([], HRESULT, "_SetSignedIntegerValue"),
            COMMETHOD([], HRESULT, "_GetSignedIntegerValue"),
            COMMETHOD([], HRESULT, "SetUnsignedLargeIntegerValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["in"], ULONGLONG, "ullValue")),
            COMMETHOD([], HRESULT, "GetUnsignedLargeIntegerValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["out"], POINTER(ULONGLONG), "pullValue")),
            COMMETHOD([], HRESULT, "_SetSignedLargeIntegerValue"),
            COMMETHOD([], HRESULT, "_GetSignedLargeIntegerValue"),
            COMMETHOD([], HRESULT, "_SetFloatValue"),
            COMMETHOD([], HRESULT, "_GetFloatValue"),
            COMMETHOD([], HRESULT, "_SetErrorValue"),
            COMMETHOD([], HRESULT, "_GetErrorValue"),
            COMMETHOD([], HRESULT, "_SetKeyValue"),
            COMMETHOD([], HRESULT, "_GetKeyValue"),
            COMMETHOD([], HRESULT, "_SetBoolValue"),
            COMMETHOD([], HRESULT, "_GetBoolValue"),
            COMMETHOD([], HRESULT, "_SetIPortableDeviceValuesValue"),
            COMMETHOD([], HRESULT, "_GetIPortableDeviceValuesValue"),
            COMMETHOD([], HRESULT, "SetStringValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["in"], LPWSTR, "pszValue")),
            COMMETHOD([], HRESULT, "GetStringValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["out"], POINTER(ctypes.c_void_p), "ppszValue")),
            COMMETHOD([], HRESULT, "_SetGuidValue"),
            COMMETHOD([], HRESULT, "GetGuidValue",
                (["in"], POINTER(PROPERTYKEY), "key"),
                (["out"], POINTER(GUID), "pValue")),
            COMMETHOD([], HRESULT, "_SetBufferValue"),
            COMMETHOD([], HRESULT, "_GetBufferValue"),
            COMMETHOD([], HRESULT, "_SetIPortableDeviceValuesCollectionValue"),
            COMMETHOD([], HRESULT, "_GetIPortableDeviceValuesCollectionValue"),
            COMMETHOD([], HRESULT, "GetCount",
                (["out"], POINTER(DWORD), "pcelt")),
            COMMETHOD([], HRESULT, "GetAt",
                (["in"], DWORD, "dwIndex"),
                (["out"], POINTER(PROPERTYKEY), "pKey"),
                (["out"], POINTER(PROPVARIANT), "pValue")),
            COMMETHOD([], HRESULT, "_RemoveValue"),
            COMMETHOD([], HRESULT, "_CopyValuesFromPropertyStore"),
            COMMETHOD([], HRESULT, "_CopyValuesToPropertyStore"),
            COMMETHOD([], HRESULT, "Clear"),
        ]

    class IPortableDeviceKeyCollection(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceKeyCollection)
        _methods_ = [
            COMMETHOD([], HRESULT, "GetCount",
                (["out"], POINTER(DWORD), "pcElems")),
            COMMETHOD([], HRESULT, "GetAt",
                (["in"], DWORD, "dwIndex"),
                (["out"], POINTER(PROPERTYKEY), "pKey")),
            COMMETHOD([], HRESULT, "Add",
                (["in"], POINTER(PROPERTYKEY), "Key")),
            COMMETHOD([], HRESULT, "Clear"),
            COMMETHOD([], HRESULT, "RemoveAt",
                (["in"], DWORD, "dwIndex")),
        ]

    class IEnumPortableDeviceObjectIDs(IUnknown):
        _iid_ = GUID(IID_IEnumPortableDeviceObjectIDs)
        _methods_ = [
            COMMETHOD([], HRESULT, "Next",
                (["in"], ULONG, "cObjects"),
                (["out"], POINTER(LPWSTR), "pObjIDs"),
                (["out"], POINTER(ULONG), "pcFetched")),
            COMMETHOD([], HRESULT, "Skip",
                (["in"], ULONG, "cObjects")),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "Clone",
                (["out"], POINTER(POINTER(IUnknown)), "ppEnum")),
            COMMETHOD([], HRESULT, "Cancel"),
        ]

    class IPortableDeviceProperties(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceProperties)
        _methods_ = [
            COMMETHOD([], HRESULT, "_GetSupportedProperties"),
            COMMETHOD([], HRESULT, "_GetPropertyAttributes"),
            COMMETHOD([], HRESULT, "GetValues",
                (["in"], LPWSTR, "pszObjectID"),
                (["in"], POINTER(IPortableDeviceKeyCollection), "pKeysToRetrieve"),
                (["out"], POINTER(POINTER(IPortableDeviceValues)), "ppValues")),
            COMMETHOD([], HRESULT, "_SetValues"),
            COMMETHOD([], HRESULT, "_Delete"),
            COMMETHOD([], HRESULT, "Cancel"),
        ]

    class ISequentialStream(IUnknown):
        _iid_ = GUID("{0C733A30-2A1C-11CE-ADE5-00AA0044773D}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Read",
                (["in"], ctypes.c_void_p, "pv"),
                (["in"], ULONG, "cb"),
                (["out"], POINTER(ULONG), "pcbRead")),
            COMMETHOD([], HRESULT, "Write",
                (["in"], ctypes.c_void_p, "pv"),
                (["in"], ULONG, "cb"),
                (["out"], POINTER(ULONG), "pcbWritten")),
        ]

    class IStream(ISequentialStream):
        _iid_ = GUID(IID_IStream)
        _methods_ = [
            COMMETHOD([], HRESULT, "Seek",
                (["in"], ctypes.c_longlong, "dlibMove"),
                (["in"], DWORD, "dwOrigin"),
                (["out"], POINTER(ctypes.c_ulonglong), "plibNewPosition")),
            COMMETHOD([], HRESULT, "SetSize",
                (["in"], ctypes.c_ulonglong, "libNewSize")),
            COMMETHOD([], HRESULT, "CopyTo",
                (["in"], POINTER(IUnknown), "pstm"),
                (["in"], ctypes.c_ulonglong, "cb"),
                (["out"], POINTER(ctypes.c_ulonglong), "pcbRead"),
                (["out"], POINTER(ctypes.c_ulonglong), "pcbWritten")),
            COMMETHOD([], HRESULT, "Commit",
                (["in"], DWORD, "grfCommitFlags")),
            COMMETHOD([], HRESULT, "Revert"),
            COMMETHOD([], HRESULT, "LockRegion",
                (["in"], ctypes.c_ulonglong, "libOffset"),
                (["in"], ctypes.c_ulonglong, "cb"),
                (["in"], DWORD, "dwLockType")),
            COMMETHOD([], HRESULT, "UnlockRegion",
                (["in"], ctypes.c_ulonglong, "libOffset"),
                (["in"], ctypes.c_ulonglong, "cb"),
                (["in"], DWORD, "dwLockType")),
            COMMETHOD([], HRESULT, "Stat",
                (["out"], ctypes.c_void_p, "pstatstg"),
                (["in"], DWORD, "grfStatFlag")),
            COMMETHOD([], HRESULT, "Clone",
                (["out"], POINTER(POINTER(IUnknown)), "ppstm")),
        ]

    class IPortableDeviceResources(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceResources)
        _methods_ = [
            COMMETHOD([], HRESULT, "_GetSupportedResources"),
            COMMETHOD([], HRESULT, "_GetResourceAttributes"),
            COMMETHOD([], HRESULT, "GetStream",
                (["in"], LPWSTR, "pszObjectID"),
                (["in"], POINTER(PROPERTYKEY), "Key"),
                (["in"], DWORD, "dwMode"),
                (["in", "out"], POINTER(DWORD), "pdwOptimalBufferSize"),
                (["out"], POINTER(POINTER(IStream)), "ppStream")),
            COMMETHOD([], HRESULT, "_Delete"),
            COMMETHOD([], HRESULT, "Cancel"),
            COMMETHOD([], HRESULT, "_CreateResource"),
        ]

    class IPortableDeviceContent(IUnknown):
        _iid_ = GUID(IID_IPortableDeviceContent)
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumObjects",
                (["in"], DWORD, "dwFlags"),
                (["in"], LPWSTR, "pszParentObjectID"),
                (["in"], ctypes.c_void_p, "pFilter"),
                (["out"], POINTER(POINTER(IEnumPortableDeviceObjectIDs)), "ppEnum")),
            COMMETHOD([], HRESULT, "Properties",
                (["out"], POINTER(POINTER(IPortableDeviceProperties)), "ppProperties")),
            COMMETHOD([], HRESULT, "Transfer",
                (["out"], POINTER(POINTER(IPortableDeviceResources)), "ppResources")),
            COMMETHOD([], HRESULT, "_CreateObjectWithPropertiesOnly"),
            COMMETHOD([], HRESULT, "_CreateObjectWithPropertiesAndData"),
            COMMETHOD([], HRESULT, "_Delete"),
            COMMETHOD([], HRESULT, "_GetObjectIDsFromPersistentUniqueIDs"),
            COMMETHOD([], HRESULT, "Cancel"),
            COMMETHOD([], HRESULT, "_Move"),
            COMMETHOD([], HRESULT, "_Copy"),
        ]

    class IPortableDevice(IUnknown):
        _iid_ = GUID(IID_IPortableDevice)
        _methods_ = [
            COMMETHOD([], HRESULT, "Open",
                (["in"], LPWSTR, "pszPnPDeviceID"),
                (["in"], POINTER(IPortableDeviceValues), "pClientInfo")),
            COMMETHOD([], HRESULT, "Content",
                (["out"], POINTER(POINTER(IPortableDeviceContent)), "ppContent")),
            COMMETHOD([], HRESULT, "_Capabilities"),
            COMMETHOD([], HRESULT, "Cancel"),
            COMMETHOD([], HRESULT, "Close"),
            COMMETHOD([], HRESULT, "_Advise"),
            COMMETHOD([], HRESULT, "_Unadvise"),
            COMMETHOD([], HRESULT, "_GetPnPDeviceID"),
        ]


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class MTPObject:
    object_id: str
    name: str
    is_folder: bool
    parent_id: str = ""
    size: int = 0
    modified: Optional[datetime.datetime] = None
    created: Optional[datetime.datetime] = None
    content_type_guid: str = ""
    virtual_path: str = ""  # e.g. "DCIM/Camera/IMG_001.jpg"


@dataclass
class MTPDeviceInfo:
    pnp_id: str
    friendly_name: str
    manufacturer: str = ""
    description: str = ""


# ── Helper: COM string free ────────────────────────────────────────────────────
_ole32 = ctypes.windll.ole32


def _free_com_str(ptr: int):
    if ptr:
        _ole32.CoTaskMemFree(ctypes.c_void_p(ptr))


def _get_string_from_ptr(ptr: int) -> str:
    if not ptr:
        return ""
    val = ctypes.wstring_at(ptr)
    _free_com_str(ptr)
    return val


# ── WPD Property Key builder ───────────────────────────────────────────────────
def _make_key(tup: tuple) -> PROPERTYKEY:
    return PROPERTYKEY.from_tuple(tup)


def _make_resource_key() -> PROPERTYKEY:
    pk = PROPERTYKEY()
    pk.fmtid = GUID(WPD_RESOURCE_DEFAULT_FMTID)
    pk.pid   = 0
    return pk


# ── WPD Key Collection builder ─────────────────────────────────────────────────
def _build_key_collection(*keys: tuple) -> "POINTER(IPortableDeviceKeyCollection)":
    kc = comtypes.client.CreateObject(
        CLSID_PortableDeviceKeyCollection,
        interface=IPortableDeviceKeyCollection,
        clsctx=comtypes.CLSCTX_INPROC_SERVER,
    )
    for k in keys:
        pk = _make_key(k)
        kc.Add(pk)
    return kc


# ── Main WPD wrapper class ─────────────────────────────────────────────────────
class WPDDevice:
    """
    High-level wrapper around one WPD/MTP connected device.
    """

    CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB read chunks

    def __init__(self, pnp_id: str, friendly_name: str):
        if not _COMTYPES_AVAILABLE:
            raise RuntimeError("comtypes not available")
        self.pnp_id = pnp_id
        self.friendly_name = friendly_name
        self._device: Optional[IPortableDevice] = None
        self._content: Optional[IPortableDeviceContent] = None
        self._props: Optional[IPortableDeviceProperties] = None
        self._resources: Optional[IPortableDeviceResources] = None

    def open(self):
        """Open the device for reading."""
        # Build client info values object
        client_info = comtypes.client.CreateObject(
            CLSID_PortableDeviceValues,
            interface=IPortableDeviceValues,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        name_key = _make_key(WPD_CLIENT_NAME)
        maj_key  = _make_key(WPD_CLIENT_MAJOR_VERSION)
        min_key  = _make_key(WPD_CLIENT_MINOR_VERSION)
        rev_key  = _make_key(WPD_CLIENT_REVISION)

        client_info.SetStringValue(name_key, "PhoneBackupManager")
        client_info.SetUnsignedIntegerValue(maj_key, 1)
        client_info.SetUnsignedIntegerValue(min_key, 0)
        client_info.SetUnsignedIntegerValue(rev_key, 0)

        device = comtypes.client.CreateObject(
            "{728A21C5-3D9E-48D7-9810-864848F0F404}",  # CLSID_PortableDevice
            interface=IPortableDevice,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        device.Open(self.pnp_id, client_info)
        self._device = device

        content_ptr = POINTER(IPortableDeviceContent)()
        device.Content(content_ptr)
        self._content = content_ptr

        props_ptr = POINTER(IPortableDeviceProperties)()
        content_ptr.Properties(props_ptr)
        self._props = props_ptr

        resources_ptr = POINTER(IPortableDeviceResources)()
        content_ptr.Transfer(resources_ptr)
        self._resources = resources_ptr

        logger.info(f"WPD device opened: {self.friendly_name}")

    def close(self):
        if self._device:
            try:
                self._device.Close()
            except Exception:
                pass
        self._device = None
        self._content = None
        self._props   = None
        self._resources = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.close()

    # ── Object enumeration ──────────────────────────────────────────────────

    def list_children(self, parent_id: str = WPD_DEVICE_OBJECT_ID) -> List[str]:
        """Return list of child object IDs for the given parent."""
        if not self._content:
            return []
        enum_ptr = POINTER(IEnumPortableDeviceObjectIDs)()
        try:
            self._content.EnumObjects(0, parent_id, None, enum_ptr)
        except comtypes.COMError:
            return []

        ids: List[str] = []
        BATCH = 32
        while True:
            batch = (LPWSTR * BATCH)()
            fetched = ULONG(0)
            try:
                hr = enum_ptr.Next(BATCH, batch, ctypes.byref(fetched))
            except comtypes.COMError:
                break
            for i in range(fetched.value):
                if batch[i]:
                    ids.append(batch[i])
            if fetched.value < BATCH:
                break
        return ids

    def get_object_info(self, object_id: str) -> Optional[MTPObject]:
        """Retrieve metadata for a single object."""
        if not self._props:
            return None
        try:
            kc = _build_key_collection(
                WPD_OBJECT_NAME,
                WPD_OBJECT_ORIGINAL_FILE_NAME,
                WPD_OBJECT_CONTENT_TYPE,
                WPD_OBJECT_SIZE,
                WPD_OBJECT_DATE_MODIFIED,
                WPD_OBJECT_DATE_CREATED,
                WPD_OBJECT_PARENT_ID,
            )
            vals_ptr = POINTER(IPortableDeviceValues)()
            self._props.GetValues(object_id, kc, vals_ptr)
            vals = vals_ptr

            # Extract name (prefer original filename)
            name = self._get_str_value(vals, WPD_OBJECT_ORIGINAL_FILE_NAME) \
                or self._get_str_value(vals, WPD_OBJECT_NAME) \
                or object_id

            # Content type
            content_type = self._get_guid_value(vals, WPD_OBJECT_CONTENT_TYPE)
            is_folder = (content_type == WPD_CONTENT_TYPE_FOLDER.upper()
                         or content_type == WPD_CONTENT_TYPE_FOLDER
                         or content_type == WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT)

            # Size
            size = self._get_u64_value(vals, WPD_OBJECT_SIZE)

            # Dates
            modified = self._get_date_value(vals, WPD_OBJECT_DATE_MODIFIED)
            created  = self._get_date_value(vals, WPD_OBJECT_DATE_CREATED)

            parent = self._get_str_value(vals, WPD_OBJECT_PARENT_ID) or ""

            return MTPObject(
                object_id=object_id,
                name=name,
                is_folder=is_folder,
                parent_id=parent,
                size=size,
                modified=modified,
                created=created,
                content_type_guid=content_type or "",
            )
        except comtypes.COMError as e:
            logger.debug(f"get_object_info failed for {object_id}: {e}")
            return None

    # ── Property readers ────────────────────────────────────────────────────

    def _get_str_value(self, vals: IPortableDeviceValues, key_tup: tuple) -> Optional[str]:
        pk = _make_key(key_tup)
        ptr = ctypes.c_void_p(0)
        try:
            vals.GetStringValue(pk, ptr)
            return _get_string_from_ptr(ptr.value)
        except comtypes.COMError:
            return None

    def _get_guid_value(self, vals: IPortableDeviceValues, key_tup: tuple) -> Optional[str]:
        pk = _make_key(key_tup)
        g = GUID()
        try:
            vals.GetGuidValue(pk, g)
            return str(g).upper()
        except comtypes.COMError:
            return None

    def _get_u64_value(self, vals: IPortableDeviceValues, key_tup: tuple) -> int:
        pk = _make_key(key_tup)
        v = ULONGLONG(0)
        try:
            vals.GetUnsignedLargeIntegerValue(pk, ctypes.byref(v))
            return v.value
        except comtypes.COMError:
            return 0

    def _get_date_value(self, vals: IPortableDeviceValues, key_tup: tuple) -> Optional[datetime.datetime]:
        """Dates in WPD may come as string or VT_DATE. Try string first."""
        s = self._get_str_value(vals, key_tup)
        if s:
            for fmt in ("%Y/%m/%d:%H:%M:%S.%f", "%Y/%m/%d:%H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.datetime.strptime(s[:len(fmt)], fmt)
                except (ValueError, TypeError):
                    pass
        return None

    # ── File streaming ──────────────────────────────────────────────────────

    def copy_file(
        self,
        object_id: str,
        dest_path: str,
        progress_cb=None,
        cancel_check=None,
    ) -> bool:
        """
        Copy a file from the MTP device to dest_path on the PC.
        progress_cb(bytes_written, total_size) called per chunk.
        cancel_check() → True means cancel.
        Returns True on success.
        """
        if not self._resources:
            return False

        resource_key = _make_resource_key()
        buf_size = DWORD(self.CHUNK_SIZE)
        stream_ptr = POINTER(IStream)()

        try:
            self._resources.GetStream(object_id, resource_key, STGM_READ, ctypes.byref(buf_size), stream_ptr)
        except comtypes.COMError as e:
            logger.error(f"GetStream failed for {object_id}: {e}")
            return False

        stream = stream_ptr
        read_size = max(buf_size.value, self.CHUNK_SIZE)
        buf = (ctypes.c_char * read_size)()

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        total_written = 0

        try:
            with open(dest_path, "wb") as f:
                while True:
                    if cancel_check and cancel_check():
                        logger.info(f"Copy cancelled: {object_id}")
                        return False
                    fetched = ULONG(0)
                    try:
                        stream.Read(buf, read_size, ctypes.byref(fetched))
                    except comtypes.COMError as e:
                        if fetched.value == 0:
                            break
                        logger.error(f"Stream read error: {e}")
                        return False
                    if fetched.value == 0:
                        break
                    f.write(bytes(buf[:fetched.value]))
                    total_written += fetched.value
                    if progress_cb:
                        progress_cb(total_written)
            return True
        except OSError as e:
            logger.error(f"File write error: {dest_path}: {e}")
            return False

    def walk(
        self,
        parent_id: str = WPD_DEVICE_OBJECT_ID,
        virtual_path: str = "",
        depth: int = 0,
        max_depth: int = 20,
        excluded_paths: Optional[set] = None,
    ) -> Iterator[MTPObject]:
        """
        Recursively walk the device object tree.
        Yields MTPObject for every file encountered.
        """
        if depth > max_depth:
            return
        try:
            child_ids = self.list_children(parent_id)
        except Exception as e:
            logger.debug(f"list_children error at {parent_id}: {e}")
            return

        for child_id in child_ids:
            obj = self.get_object_info(child_id)
            if obj is None:
                continue
            child_path = f"{virtual_path}/{obj.name}" if virtual_path else obj.name
            obj.virtual_path = child_path

            # Check exclusions
            if excluded_paths:
                skip = False
                for ex in excluded_paths:
                    if child_path.lower().startswith(ex.lower()):
                        skip = True
                        break
                if skip:
                    continue

            if obj.is_folder:
                yield from self.walk(
                    parent_id=child_id,
                    virtual_path=child_path,
                    depth=depth + 1,
                    max_depth=max_depth,
                    excluded_paths=excluded_paths,
                )
            else:
                yield obj


# ── Device enumeration ────────────────────────────────────────────────────────

def list_mtp_devices() -> List[MTPDeviceInfo]:
    """
    Enumerate all connected WPD/MTP devices.
    Returns a list of MTPDeviceInfo objects.
    """
    if not _COMTYPES_AVAILABLE:
        return []
    try:
        mgr = comtypes.client.CreateObject(
            CLSID_PortableDeviceManager,
            interface=IPortableDeviceManager,
            clsctx=comtypes.CLSCTX_INPROC_SERVER,
        )
        mgr.RefreshDeviceList()

        count = DWORD(0)
        mgr.GetDevices(None, ctypes.byref(count))
        if count.value == 0:
            return []

        n = count.value
        ids = (LPWSTR * n)()
        mgr.GetDevices(ids, ctypes.byref(count))

        devices: List[MTPDeviceInfo] = []
        for i in range(n):
            pnp_id = ids[i]
            if not pnp_id:
                continue

            friendly = _get_device_string(mgr, "friendly", pnp_id)
            manufacturer = _get_device_string(mgr, "manufacturer", pnp_id)
            description = _get_device_string(mgr, "description", pnp_id)

            devices.append(MTPDeviceInfo(
                pnp_id=pnp_id,
                friendly_name=friendly or pnp_id,
                manufacturer=manufacturer,
                description=description,
            ))
            logger.info(f"Found MTP device: {friendly} ({pnp_id})")
        return devices

    except comtypes.COMError as e:
        logger.error(f"list_mtp_devices COM error: {e}")
        return []
    except Exception as e:
        logger.error(f"list_mtp_devices error: {e}")
        return []


def _get_device_string(mgr: IPortableDeviceManager, kind: str, pnp_id: str) -> str:
    """
    Retrieve a string property from the device manager.
    Uses a two-call pattern: first get required char count, then allocate and retrieve.
    """
    try:
        # First call: get the required buffer length
        length = DWORD(0)
        null_ptr = ctypes.c_void_p(0)
        if kind == "friendly":
            mgr.GetDeviceFriendlyName(pnp_id, null_ptr, ctypes.byref(length))
        elif kind == "manufacturer":
            mgr.GetDeviceManufacturer(pnp_id, null_ptr, ctypes.byref(length))
        elif kind == "description":
            mgr.GetDeviceDescription(pnp_id, null_ptr, ctypes.byref(length))
        else:
            return ""

        if length.value == 0:
            return ""

        # Second call: allocate buffer and retrieve the string
        buf = ctypes.create_unicode_buffer(length.value)
        buf_ptr = ctypes.cast(buf, ctypes.c_void_p)
        if kind == "friendly":
            mgr.GetDeviceFriendlyName(pnp_id, buf_ptr, ctypes.byref(length))
        elif kind == "manufacturer":
            mgr.GetDeviceManufacturer(pnp_id, buf_ptr, ctypes.byref(length))
        elif kind == "description":
            mgr.GetDeviceDescription(pnp_id, buf_ptr, ctypes.byref(length))

        return buf.value
    except comtypes.COMError:
        return ""
    except Exception:
        return ""


def open_device(device_info: MTPDeviceInfo) -> WPDDevice:
    """Open and return a WPDDevice for reading."""
    dev = WPDDevice(device_info.pnp_id, device_info.friendly_name)
    dev.open()
    return dev
