# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: pogoprotos/settings/gps_settings.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='pogoprotos/settings/gps_settings.proto',
  package='pogoprotos.settings',
  syntax='proto3',
  serialized_options=None,
  serialized_pb=_b('\n&pogoprotos/settings/gps_settings.proto\x12\x13pogoprotos.settings\"\xbb\x01\n\x0bGpsSettings\x12/\n\'driving_warning_speed_meters_per_second\x18\x01 \x01(\x02\x12(\n driving_warning_cooldown_minutes\x18\x02 \x01(\x02\x12-\n%driving_speed_sample_interval_seconds\x18\x03 \x01(\x02\x12\"\n\x1a\x64riving_speed_sample_count\x18\x04 \x01(\x05\x62\x06proto3')
)




_GPSSETTINGS = _descriptor.Descriptor(
  name='GpsSettings',
  full_name='pogoprotos.settings.GpsSettings',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='driving_warning_speed_meters_per_second', full_name='pogoprotos.settings.GpsSettings.driving_warning_speed_meters_per_second', index=0,
      number=1, type=2, cpp_type=6, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='driving_warning_cooldown_minutes', full_name='pogoprotos.settings.GpsSettings.driving_warning_cooldown_minutes', index=1,
      number=2, type=2, cpp_type=6, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='driving_speed_sample_interval_seconds', full_name='pogoprotos.settings.GpsSettings.driving_speed_sample_interval_seconds', index=2,
      number=3, type=2, cpp_type=6, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='driving_speed_sample_count', full_name='pogoprotos.settings.GpsSettings.driving_speed_sample_count', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=64,
  serialized_end=251,
)

DESCRIPTOR.message_types_by_name['GpsSettings'] = _GPSSETTINGS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

GpsSettings = _reflection.GeneratedProtocolMessageType('GpsSettings', (_message.Message,), dict(
  DESCRIPTOR = _GPSSETTINGS,
  __module__ = 'pogoprotos.settings.gps_settings_pb2'
  # @@protoc_insertion_point(class_scope:pogoprotos.settings.GpsSettings)
  ))
_sym_db.RegisterMessage(GpsSettings)


# @@protoc_insertion_point(module_scope)
