"""Credential references only. Values stay in environment or the macOS Keychain."""
import ctypes
import os
import sys

class SecretStore:
    def get(self, reference):
        if not isinstance(reference,str) or ':' not in reference:
            raise ValueError('Use a secret reference, not a credential value')
        kind, name = reference.split(':',1)
        if kind == 'env':
            if not name or not name.replace('_','').isalnum():
                raise ValueError('Invalid environment reference')
            return os.environ.get(name)
        if kind != 'keychain' or sys.platform != 'darwin' or not name:
            raise ValueError('Secret provider is unavailable')
        security = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        service = b'workspace-engine'; account = name.encode()
        length = ctypes.c_uint32(); data = ctypes.c_void_p()
        find = security.SecKeychainFindGenericPassword
        find.argtypes = [ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p]
        find.restype = ctypes.c_int32
        status = find(None,len(service),service,len(account),account,ctypes.byref(length),ctypes.byref(data),None)
        if status == -25300:
            return None
        if status:
            raise RuntimeError('Keychain access failed')
        try:
            return ctypes.string_at(data,length.value).decode()
        finally:
            security.SecKeychainItemFreeContent.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
            security.SecKeychainItemFreeContent.restype=ctypes.c_int32
            security.SecKeychainItemFreeContent(None,data)
    def set_keychain(self, name, value):
        if sys.platform != 'darwin':
            raise RuntimeError('Keychain is available on macOS only')
        if not name or not value:
            raise ValueError('A name and value are required')
        security = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        core = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        service = b'workspace-engine'; account = name.encode(); raw = value.encode(); item = ctypes.c_void_p()
        find = security.SecKeychainFindGenericPassword
        find.argtypes = [ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
        find.restype = ctypes.c_int32
        status = find(None,len(service),service,len(account),account,None,None,ctypes.byref(item))
        if status == 0:
            modify=security.SecKeychainItemModifyAttributesAndData
            modify.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p];modify.restype=ctypes.c_int32
            try: status=modify(item,None,len(raw),raw)
            finally:
                core.CFRelease.argtypes=[ctypes.c_void_p];core.CFRelease.restype=None
                core.CFRelease(item)
        elif status == -25300:
            add=security.SecKeychainAddGenericPassword
            add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_uint32,ctypes.c_char_p,ctypes.c_void_p];add.restype=ctypes.c_int32
            status=add(None,len(service),service,len(account),account,len(raw),raw,None)
        if status:
            raise RuntimeError('Could not store the credential in Keychain')
