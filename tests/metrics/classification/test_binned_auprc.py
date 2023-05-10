# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import List, Optional, Union

import torch
from torcheval.metrics.classification.binned_auprc import (
    BinaryBinnedAUPRC,
    MulticlassBinnedAUPRC,
    MultilabelBinnedAUPRC,
)
from torcheval.metrics.functional.classification import (
    binary_auprc,
    multiclass_auprc,
    multilabel_auprc,
)
from torcheval.utils import random_data as rd
from torcheval.utils.test_utils.metric_class_tester import (
    BATCH_SIZE,
    MetricClassTester,
    NUM_TOTAL_UPDATES,
)


class TestBinaryBinnedAUPRC(MetricClassTester):
    def _test_binned_auprc_class_with_input(
        self,
        update_input: torch.Tensor,
        update_target: torch.Tensor,
        num_tasks: int,
        threshold: Union[int, List[float], torch.Tensor],
        compute_result: torch.Tensor,
    ) -> None:
        self.run_class_implementation_tests(
            metric=BinaryBinnedAUPRC(num_tasks=num_tasks, threshold=threshold),
            state_names={"inputs", "targets"},
            update_kwargs={
                "input": update_input,
                "target": update_target,
            },
            compute_result=compute_result,
        )

    def test_binned_auprc_class_valid_input(self) -> None:
        torch.manual_seed(123)
        # test case with num_tasks=1
        input = torch.randint(high=2, size=(NUM_TOTAL_UPDATES, BATCH_SIZE))
        target = torch.randint(high=2, size=(NUM_TOTAL_UPDATES, BATCH_SIZE))
        threshold = 5
        self._test_binned_auprc_class_with_input(
            input,
            target,
            num_tasks=1,
            threshold=threshold,
            compute_result=torch.tensor(0.5117788314819336),
        )

        # test case with num_tasks=2
        torch.manual_seed(123)
        num_tasks = 2
        input = torch.rand(NUM_TOTAL_UPDATES, num_tasks, BATCH_SIZE)
        target = torch.randint(high=2, size=(NUM_TOTAL_UPDATES, num_tasks, BATCH_SIZE))
        threshold = 5
        self._test_binned_auprc_class_with_input(
            input,
            target,
            num_tasks=num_tasks,
            threshold=threshold,
            compute_result=torch.tensor([0.5810506343841553, 0.5106710195541382]),
        )

        # test case with different update shape
        num_classes = 2
        threshold = 5
        torch.manual_seed(123)
        update_input = [
            torch.rand(5),
            torch.rand(8),
            torch.rand(2),
            torch.rand(5),
        ]

        update_target = [
            torch.randint(high=num_classes, size=(5,)),
            torch.randint(high=num_classes, size=(8,)),
            torch.randint(high=num_classes, size=(2,)),
            torch.randint(high=num_classes, size=(5,)),
        ]
        compute_result = torch.tensor(0.42704516649246216)

        self.run_class_implementation_tests(
            metric=BinaryBinnedAUPRC(threshold=threshold),
            state_names={"inputs", "targets"},
            update_kwargs={
                "input": update_input,
                "target": update_target,
            },
            compute_result=compute_result,
            num_total_updates=4,
            num_processes=2,
        )

    def test_with_randomized_binary_data_getter_single_task(self) -> None:
        batch_size = 4
        num_bins = 5

        for _ in range(10):
            update_input, update_target = rd.get_rand_data_binary(
                NUM_TOTAL_UPDATES, 1, batch_size
            )
            threshold = torch.cat([torch.tensor([0, 1]), torch.rand(num_bins - 2)])
            threshold, _ = torch.sort(threshold)
            threshold = torch.unique(threshold)

            input_positions = (
                torch.searchsorted(threshold, update_input, right=True) - 1
            )  # get thresholds not larger than each element

            # update_input, update_target original shape: [num_updates, batch_size]
            # simply reshape to a 1D tensor: [num_updates * batch_size, ]
            inputs_quantized = threshold[input_positions].reshape((-1,))
            full_target = update_target.reshape((-1,))

            compute_result = binary_auprc(
                inputs_quantized,
                full_target,
                num_tasks=1,
            )

            self._test_binned_auprc_class_with_input(
                update_input,
                update_target,
                num_tasks=1,
                threshold=threshold,
                compute_result=compute_result,
            )

    def test_with_randomized_binary_data_getter_multiple_tasks(self) -> None:
        batch_size = 4
        num_bins = 5
        num_tasks = 3

        for _ in range(10):
            update_input, update_target = rd.get_rand_data_binary(
                NUM_TOTAL_UPDATES, num_tasks, batch_size
            )
            threshold = torch.cat([torch.tensor([0, 1]), torch.rand(num_bins - 2)])
            threshold, _ = torch.sort(threshold)
            threshold = torch.unique(threshold)
            input_positions = (
                torch.searchsorted(threshold, update_input, right=True) - 1
            )  # get thresholds not larger than each element

            # update_target original shape: [num_updates, num_tasks, batch_size]
            # transpose 0, 1: [num_tasks, num_updates, batch_size]
            # then, flatten to get full_target shape: [num_tasks, num_updates * batch_size]
            inputs_quantized = threshold[input_positions].transpose(0, 1).flatten(1, 2)
            full_target = update_target.transpose(0, 1).flatten(1, 2)

            compute_result = binary_auprc(
                inputs_quantized,
                full_target,
                num_tasks=num_tasks,
            )

            self._test_binned_auprc_class_with_input(
                update_input,
                update_target,
                num_tasks=num_tasks,
                threshold=threshold,
                compute_result=compute_result,
            )

    def test_binary_binned_auprc_class_invalid_input(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks` has to be at least 1.",
        ):
            BinaryBinnedAUPRC(num_tasks=-1)

        with self.assertRaisesRegex(
            ValueError,
            "The `input` and `target` should have the same shape, "
            r"got shapes torch.Size\(\[4\]\) and torch.Size\(\[3\]\).",
        ):
            metric = BinaryBinnedAUPRC()
            metric.update(torch.rand(4), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 1`, `input` is expected to be 1D or 2D tensor, but got shape "
            r"torch.Size\(\[\]\).",
        ):
            metric = BinaryBinnedAUPRC()
            metric.update(torch.rand(size=()), torch.rand(size=()))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 1`, `input` is expected to be 1D or 2D tensor, but got shape "
            r"torch.Size\(\[4, 5, 5\]\).",
        ):
            metric = BinaryBinnedAUPRC()
            metric.update(torch.rand(4, 5, 5), torch.rand(4, 5, 5))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 2`, `input` is expected to be 2D tensor, but got shape "
            r"torch.Size\(\[4, 5, 5\]\).",
        ):
            metric = BinaryBinnedAUPRC(num_tasks=2)
            metric.update(torch.rand(4, 5, 5), torch.rand(4, 5, 5))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 2`, `input`'s shape is expected to be "
            r"\(2, num_samples\), but got shape torch.Size\(\[4, 5\]\).",
        ):
            metric = BinaryBinnedAUPRC(num_tasks=2)
            metric.update(torch.rand(4, 5), torch.rand(4, 5))

        with self.assertRaisesRegex(
            ValueError, "The `threshold` should be a sorted tensor."
        ):
            metric = BinaryBinnedAUPRC(
                threshold=torch.tensor([0.1, 0.2, 0.5, 0.7, 0.6]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"The values in `threshold` should be in the range of \[0, 1\].",
        ):
            metric = BinaryBinnedAUPRC(
                threshold=torch.tensor([-0.1, 0.2, 0.5, 0.7]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"`threshold` should be 1-dimensional, but got 2D tensor.",
        ):
            metric = BinaryBinnedAUPRC(
                threshold=torch.tensor([[-0.1, 0.2, 0.5, 0.7], [0.0, 0.4, 0.6, 1.0]]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"First value in `threshold` should be 0.",
        ):
            metric = BinaryBinnedAUPRC(
                threshold=torch.tensor([0.1, 0.2, 0.5, 1.0]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"Last value in `threshold` should be 1.",
        ):
            metric = BinaryBinnedAUPRC(
                threshold=torch.tensor([0.0, 0.2, 0.5, 0.9]),
            )


class TestMulticlassBinnedAUPRC(MetricClassTester):
    def _test_multiclass_binned_auprc_class_with_input(
        self,
        update_input: Union[torch.Tensor, List[torch.Tensor]],
        update_target: Union[torch.Tensor, List[torch.Tensor]],
        compute_result: torch.Tensor,
        num_classes: int,
        threshold: Union[int, List[float], torch.Tensor],
        average: Optional[str],
    ) -> None:
        for optimization in ("vectorized", "memory"):
            self.run_class_implementation_tests(
                metric=MulticlassBinnedAUPRC(
                    num_classes=num_classes,
                    threshold=threshold,
                    average=average,
                    optimization=optimization,
                ),
                state_names={"num_tp", "num_fp", "num_fn"},
                update_kwargs={
                    "input": update_input,
                    "target": update_target,
                },
                compute_result=compute_result,
                num_total_updates=len(update_input),
                num_processes=2,
            )

    def test_binned_auprc_class_base(self) -> None:
        num_classes = 4
        threshold = 5
        torch.manual_seed(123)
        input = 10 * torch.rand(NUM_TOTAL_UPDATES, BATCH_SIZE, num_classes)
        input = input.abs() / input.abs().sum(dim=-1, keepdim=True)
        target = torch.randint(high=num_classes, size=(NUM_TOTAL_UPDATES, BATCH_SIZE))

        compute_result = torch.tensor(0.2522818148136139)

        self._test_multiclass_binned_auprc_class_with_input(
            input, target, compute_result, num_classes, threshold, average="macro"
        )

    def test_binned_auprc_average_options(self) -> None:
        input = torch.tensor(
            [
                [[0.16, 0.04, 0.8]],
                [[0.1, 0.7, 0.2]],
                [[0.16, 0.8, 0.04]],
                [[0.16, 0.04, 0.8]],
            ]
        )
        target = torch.tensor([[0], [0], [1], [2]])
        num_classes = 3
        threshold = 5

        compute_result = torch.tensor(2 / 3)
        self._test_multiclass_binned_auprc_class_with_input(
            input, target, compute_result, num_classes, threshold, average="macro"
        )

        compute_result = torch.tensor([0.5000, 1.0000, 0.5000])
        self._test_multiclass_binned_auprc_class_with_input(
            input, target, compute_result, num_classes, threshold, average=None
        )

    def test_with_randomized_data_getter(self) -> None:
        num_classes = 3
        batch_size = 4
        num_bins = 5

        for _ in range(4):
            input, target = rd.get_rand_data_multiclass(1, num_classes, batch_size)
            threshold = torch.cat([torch.tensor([0, 1]), torch.rand(num_bins - 2)])

            threshold, _ = torch.sort(threshold)
            threshold = torch.unique(threshold)

            input_positions = torch.searchsorted(
                threshold, input, right=False
            )  # get thresholds not larger than each element
            inputs_quantized = threshold[input_positions]

            for average in (None, "macro"):
                compute_result = multiclass_auprc(
                    inputs_quantized,
                    target,
                    num_classes=num_classes,
                    average=average,
                )
                self._test_multiclass_binned_auprc_class_with_input(
                    input.unsqueeze(1),
                    target.unsqueeze(1),
                    compute_result,
                    num_classes,
                    threshold,
                    average,
                )

    def test_binned_auprc_class_update_input_shape_different(self) -> None:
        torch.manual_seed(123)
        num_classes = 3
        update_input = [
            torch.rand(5, num_classes),
            torch.rand(8, num_classes),
            torch.rand(2, num_classes),
            torch.rand(5, num_classes),
        ]
        update_input = [
            input.abs() / input.abs().sum(dim=-1, keepdim=True)
            for input in update_input
        ]
        update_target = [
            torch.randint(high=num_classes, size=(5,)),
            torch.randint(high=num_classes, size=(8,)),
            torch.randint(high=num_classes, size=(2,)),
            torch.randint(high=num_classes, size=(5,)),
        ]
        threshold = 5
        compute_result = torch.tensor(0.372433333333333)

        self._test_multiclass_binned_auprc_class_with_input(
            update_input,
            update_target,
            compute_result,
            num_classes,
            threshold,
            average="macro",
        )

    def test_binned_auprc_class_invalid_input(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "`average` was not in the allowed value of .*, got micro."
        ):
            metric = MulticlassBinnedAUPRC(num_classes=4, average="micro")

        with self.assertRaisesRegex(ValueError, "`num_classes` has to be at least 2."):
            metric = MulticlassBinnedAUPRC(num_classes=1)

        with self.assertRaisesRegex(
            ValueError,
            "The `input` and `target` should have the same first dimension, "
            r"got shapes torch.Size\(\[4, 2\]\) and torch.Size\(\[3\]\).",
        ):
            metric = MulticlassBinnedAUPRC(num_classes=3)
            metric.update(torch.rand(4, 2), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError,
            "target should be a one-dimensional tensor, "
            r"got shape torch.Size\(\[3, 2\]\).",
        ):
            metric = MulticlassBinnedAUPRC(num_classes=2)
            metric.update(torch.rand(3, 2), torch.rand(3, 2))

        with self.assertRaisesRegex(
            ValueError,
            r"input should have shape of \(num_sample, num_classes\), "
            r"got torch.Size\(\[3, 4\]\) and num_classes=2.",
        ):
            metric = MulticlassBinnedAUPRC(num_classes=2)
            metric.update(torch.rand(3, 4), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError, "The `threshold` should be a sorted tensor."
        ):
            metric = MulticlassBinnedAUPRC(
                num_classes=4, threshold=torch.tensor([0.1, 0.2, 0.5, 0.7, 0.6])
            )

        with self.assertRaisesRegex(
            ValueError,
            r"The values in `threshold` should be in the range of \[0, 1\].",
        ):
            metric = MulticlassBinnedAUPRC(
                num_classes=4, threshold=torch.tensor([-0.1, 0.2, 0.5, 0.7])
            )

        with self.assertRaisesRegex(
            ValueError,
            r"`threshold` should be 1-dimensional, but got 2D tensor.",
        ):
            metric = MulticlassBinnedAUPRC(
                num_classes=4,
                threshold=torch.tensor([[-0.1, 0.2, 0.5, 0.7], [0.0, 0.4, 0.6, 1.0]]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"First value in `threshold` should be 0.",
        ):
            metric = MulticlassBinnedAUPRC(
                num_classes=4,
                threshold=torch.tensor([0.1, 0.2, 0.5, 1.0]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"Last value in `threshold` should be 1.",
        ):
            metric = MulticlassBinnedAUPRC(
                num_classes=4,
                threshold=torch.tensor([0.0, 0.2, 0.5, 0.9]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"Unknown memory approach: expected 'vectorized' or 'memory', but got cpu.",
        ):
            metric = (
                MulticlassBinnedAUPRC(
                    num_classes=3,
                    threshold=5,
                    optimization="cpu",
                ),
            )


class TestMultilabelBinnedAUPRC(MetricClassTester):
    def _test_multilabel_binned_auprc_class_with_input(
        self,
        update_input: Union[torch.Tensor, List[torch.Tensor]],
        update_target: Union[torch.Tensor, List[torch.Tensor]],
        compute_result: torch.Tensor,
        num_labels: int,
        threshold: Union[int, List[float], torch.Tensor],
        average: Optional[str],
    ) -> None:
        self.run_class_implementation_tests(
            metric=MultilabelBinnedAUPRC(
                num_labels=num_labels, threshold=threshold, average=average
            ),
            state_names={"num_tp", "num_fp", "num_fn"},
            update_kwargs={
                "input": update_input,
                "target": update_target,
            },
            compute_result=compute_result,
            num_total_updates=len(update_input),
            num_processes=2,
        )

    def test_multilabel_binned_auprc_class_threshold_specified_as_int(
        self,
    ) -> None:
        num_labels = 3
        input = torch.tensor(
            [
                [[0.75, 0.05, 0.35]],
                [[0.45, 0.75, 0.05]],
                [[0.05, 0.55, 0.75]],
                [[0.05, 0.65, 0.05]],
            ]
        )
        target = torch.tensor([[[1, 0, 1]], [[0, 0, 0]], [[0, 1, 1]], [[1, 1, 1]]])
        threshold = 5
        compute_result = torch.tensor([0.7500, 2 / 3, 11 / 12])
        self._test_multilabel_binned_auprc_class_with_input(
            input, target, compute_result, num_labels, threshold, None
        )

        compute_result = torch.tensor(7 / 9)
        self._test_multilabel_binned_auprc_class_with_input(
            input, target, compute_result, num_labels, threshold, "macro"
        )

        # Result should match non-binned result if there are enough thresholds
        threshold = 100
        compute_result = torch.tensor([0.7500, 7 / 12, 11 / 12])
        self._test_multilabel_binned_auprc_class_with_input(
            input, target, compute_result, num_labels, threshold, None
        )

    def test_multilabel_binned_auprc_class_threshold_specified_as_tensor(
        self,
    ) -> None:
        num_labels = 3
        input = torch.tensor(
            [
                [[0.75, 0.05, 0.35]],
                [[0.45, 0.75, 0.05]],
                [[0.05, 0.55, 0.75]],
                [[0.05, 0.65, 0.05]],
            ]
        )
        target = torch.tensor([[[1, 0, 1]], [[0, 0, 0]], [[0, 1, 1]], [[1, 1, 1]]])
        threshold = torch.tensor([0.0, 0.1, 0.4, 0.7, 0.8, 0.9, 1.0])
        compute_result = torch.tensor([0.7500, 2 / 3, 11 / 12])

        self._test_multilabel_binned_auprc_class_with_input(
            input, target, compute_result, num_labels, threshold, None
        )

        compute_result = torch.tensor(7 / 9)
        self._test_multilabel_binned_auprc_class_with_input(
            input, target, compute_result, num_labels, threshold, "macro"
        )

    def test_with_randomized_data_getter(self) -> None:
        num_labels = 3
        batch_size = 4
        num_bins = 5

        for _ in range(10):
            input, target = rd.get_rand_data_multilabel(1, num_labels, batch_size)
            threshold = torch.cat([torch.tensor([0, 1]), torch.rand(num_bins - 2)])

            threshold, _ = torch.sort(threshold)
            threshold = torch.unique(threshold)

            input_positions = torch.searchsorted(
                threshold, input, right=False
            )  # get thresholds not larger than each element
            inputs_quantized = threshold[input_positions]

            for average in (None, "macro"):
                compute_result = multilabel_auprc(
                    inputs_quantized,
                    target,
                    num_labels=num_labels,
                    average=average,
                )
                self._test_multilabel_binned_auprc_class_with_input(
                    input.unsqueeze(1),
                    target.unsqueeze(1),
                    compute_result,
                    num_labels,
                    threshold,
                    average,
                )

    def test_multilabel_binned_auprc_class_update_input_shape_different(
        self,
    ) -> None:
        torch.manual_seed(123)
        num_labels = 10
        update_input = [
            torch.rand(5, num_labels),
            torch.rand(8, num_labels),
            torch.rand(2, num_labels),
            torch.rand(5, num_labels),
        ]

        update_target = [
            torch.randint(high=num_labels, size=(5, num_labels)),
            torch.randint(high=num_labels, size=(8, num_labels)),
            torch.randint(high=num_labels, size=(2, num_labels)),
            torch.randint(high=num_labels, size=(5, num_labels)),
        ]

        threshold = 5

        compute_result = torch.tensor(0.07306567579507828)
        self._test_multilabel_binned_auprc_class_with_input(
            update_input, update_target, compute_result, num_labels, threshold, "macro"
        )

    def test_multilabel_binned_auprc_invalid_input(self) -> None:
        metric = MultilabelBinnedAUPRC(num_labels=3)
        with self.assertRaisesRegex(
            ValueError,
            "Expected both input.shape and target.shape to have the same shape"
            r" but got torch.Size\(\[4, 2\]\) and torch.Size\(\[3\]\).",
        ):
            metric.update(torch.rand(4, 2), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError,
            "input should be a two-dimensional tensor, got shape "
            r"torch.Size\(\[3\]\).",
        ):
            metric.update(torch.rand(3), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError,
            "input should have shape of "
            r"\(num_sample, num_labels\), got torch.Size\(\[4, 2\]\) and num_labels=3.",
        ):
            metric.update(torch.rand(4, 2), torch.rand(4, 2))

        with self.assertRaisesRegex(
            ValueError, "The `threshold` should be a sorted tensor."
        ):
            MultilabelBinnedAUPRC(
                num_labels=3, threshold=torch.tensor([0.1, 0.2, 0.5, 0.7, 0.6])
            )

        with self.assertRaisesRegex(
            ValueError,
            r"The values in `threshold` should be in the range of \[0, 1\].",
        ):
            MultilabelBinnedAUPRC(
                num_labels=3, threshold=torch.tensor([-0.1, 0.2, 0.5, 0.7])
            )

        with self.assertRaisesRegex(
            ValueError,
            r"The values in `threshold` should be in the range of \[0, 1\].",
        ):
            MultilabelBinnedAUPRC(
                num_labels=3, threshold=torch.tensor([0.1, 0.2, 0.5, 1.7])
            )
