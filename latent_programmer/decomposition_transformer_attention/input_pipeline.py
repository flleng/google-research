# coding=utf-8
# Copyright 2022 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""Input pipeline for Robust-fill dataset."""

import tensorflow.compat.v2 as tf

from latent_programmer.tasks.robust_fill import dsl as robust_fill_dsl
from latent_programmer.tasks.scan import scan_vocab

gfile = tf.io.gfile


def create_robust_fill_dataset_from_tf_record(file_pattern, token_id_table,
                                              char_id_table):
  """Returns an instance of tf.data.Dataset."""

  filenames = gfile.glob(file_pattern)
  raw_dataset = tf.data.TFRecordDataset(filenames)

  char_table = tf.lookup.StaticVocabularyTable(
      tf.lookup.KeyValueTensorInitializer(
          # Add padding.
          [''] + list(char_id_table.keys()),
          [0] + list(char_id_table.values()),
          key_dtype=tf.string,
          value_dtype=tf.int64),
      len(char_id_table) + 1)
  bos_token = token_id_table[robust_fill_dsl.BOS]
  eos_token = token_id_table[robust_fill_dsl.EOS]

  def _parse_fn(record):
    """Parses a record into a feature_dict."""
    feature_values = tf.io.parse_single_example(
        serialized=record,
        features={
            'i/o':
                tf.io.FixedLenFeature([], tf.string, default_value=''),
            'program_encoding':
                tf.io.FixedLenFeature([], tf.string, default_value=''),
        })

    ios = tf.strings.split(
        tf.strings.split(feature_values['i/o'], sep='>'), sep='<')

    inputs, outputs = ios.merge_dims(0, 1)[::2], ios.merge_dims(0, 1)[1::2]
    # Step 1. Parse inputs into tokens.
    inputs = tf.strings.unicode_split(inputs, 'UTF-8').to_tensor()
    inputs = char_table.lookup(inputs)  # Map characters to tokens.

    # Step 2. Parse outputs into tokens.
    split_outputs = tf.strings.unicode_split(
        tf.strings.split(outputs, sep='|'), 'UTF-8')
    outputs = split_outputs.merge_dims(1, 2).to_tensor()
    outputs = char_table.lookup(outputs)

    # Step 3. Parse program into tokens.
    program_encoding = feature_values['program_encoding']
    # Add BOS between every partial program, then add BOS followed by EOS.
    # `program_encoding` has a | between partial programs (not at the beginning
    # or end of the sequence, and no spaces around |).
    program_encoding = tf.strings.join([
        tf.strings.regex_replace(program_encoding, r'\|',
                                 ' {} '.format(bos_token)),
        ' {} {}'.format(bos_token, eos_token),
    ])
    # Parse numbers.
    program_encoding = tf.strings.split(program_encoding, sep=' ')
    program_encoding = tf.strings.to_number(
        program_encoding, out_type=tf.int32)

    return inputs, outputs, program_encoding

  dataset = raw_dataset.map(_parse_fn)
  return dataset


def create_scan_dataset_from_tf_record(file_pattern, token_id_table,
                                       char_id_table):
  """Returns an instance of tf.data.Dataset."""
  del char_id_table

  filenames = gfile.glob(file_pattern)
  raw_dataset = tf.data.TFRecordDataset(filenames)

  bos_token = token_id_table[scan_vocab.BOS]
  eos_token = token_id_table[scan_vocab.EOS]

  def _parse_fn(record):
    """Parses a record into a feature_dict."""
    feature_values = tf.io.parse_single_example(
        serialized=record,
        features={
            'input': tf.io.FixedLenFeature([], tf.string, default_value=''),
            'output': tf.io.FixedLenFeature([], tf.string, default_value=''),
        })

    # Step 1. Parse input tokens.
    input_str = feature_values['input']
    input_split = tf.strings.split(input_str, sep=' ')
    input_tokens = tf.strings.to_number(input_split, out_type=tf.int32)
    input_tokens = tf.expand_dims(input_tokens, axis=0)

    # Step 2. Create dummy "output" (analogous to RobustFill's output).
    dummy = input_tokens

    # Step 3. Parse output program into tokens.
    program = feature_values['output']
    # Add BOS between every part, then add BOS followed by EOS. `program` has a
    # | between parts (not at the beginning or end of the sequence, and no
    # spaces around |).
    program = tf.strings.join([
        tf.strings.regex_replace(program, r'\|', ' {} '.format(bos_token)),
        ' {} {}'.format(bos_token, eos_token),
    ])
    # Parse numbers.
    program = tf.strings.split(program, sep=' ')
    program = tf.strings.to_number(program, out_type=tf.int32)

    return input_tokens, dummy, program

  dataset = raw_dataset.map(_parse_fn)
  return dataset
