# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""CPU time profiler."""

import logging
from googlecloudprofiler import _profiler
from googlecloudprofiler import builder
from googlecloudprofiler import profile_pb2
import memray
from memray import FileReader
from memray.reporters.flamegraph import FlameGraphReporter
import collections

logger = logging.getLogger(__name__)


class CPUProfiler:
  """CPU time profiler.

  The profiler collects CPU time usage data and builds the data as
  a gzip-compressed profile proto.
  """

  def __init__(self, period_ms=10, dump_file_name='/usr/local/google/home/jatinagarwala/Profiler/some_output_file.bin'):
    """Constructs the CPU time profiler.

    Args:
      period_ms: An optional integer specifying the sampling interval in
      milliseconds. Defaults to 10.
    """
    self._profile_type = 'CPU'
    self._period_ms = period_ms
    self._dump_file_name = dump_file_name

  def build_stack(self, node_index, nodes, strings):
    if node_index is None:
      return []

    stack = []
    current_node_index = node_index

    while current_node_index is not None:
      if nodes['name'][current_node_index] != 0:
        stack.append((
        strings[nodes['name'][current_node_index]],
        strings[nodes['filename'][current_node_index]],
        nodes['lineno'][current_node_index],
      ))
      current_node_index = nodes['children'][current_node_index][0] if len(
      nodes['children'][current_node_index]) > 0 else None

    return list(reversed(stack))

  def profile(self, duration_ns):
    """Profiles the maximum Memory usage since the application started.

    Returns:
    A bytes object containing gzip-compressed profile proto.
    """

    # This requires that the program is run with memray and the bin output file is named "some_output_file.bin"
    with FileReader(self._dump_file_name, report_progress=True) as reader:
      snapshot = reader.get_high_watermark_allocation_records()
      memory_records = tuple(reader.get_memory_snapshots())
      reporter = FlameGraphReporter.from_snapshot(
          snapshot,
          memory_records=memory_records,
          native_traces=False,
          inverted=False,
      )

    Func = collections.namedtuple("Func", ["name", "filename"])
    Loc = collections.namedtuple("Loc", ["func_id", "line_number"])

    # Convert memray data to pprof format
    traces = collections.defaultdict(int)

    nodes = reporter.data["nodes"]
    strings = reporter.data["strings"]

    # When creating the traces dictionary.
    traces[tuple(self.build_stack(0, nodes, strings))] = nodes['value'][0]
    for i in range(len(nodes['value'])):
      traces[tuple(self.build_stack(i, nodes, strings))
            ] = nodes['value'][i]

    for i in range(len(nodes['value'])):
      if nodes['value'][i] > 0:
        stack = self.build_stack(i, nodes, strings)
        # print("Stack for node", i, ":", stack)
        traces[tuple(stack)] += nodes['value'][i]

    return self._build_profile(duration_ns, traces)

  def _profile(self, duration_ns):
    return _profiler.profile_cpu(duration_ns, self._period_ms)

  def _build_profile(self, duration_ns, traces):
    profile_builder = builder.Builder()
    profile_builder.populate_profile(traces, self._profile_type, 'nanoseconds',
                                      self._period_ms * 1000 * 1000, duration_ns)
    return profile_builder.emit()
