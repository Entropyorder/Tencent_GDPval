import numpy as np
import pytest

from finance_forensics.query_selection import randomized_farthest_indices


def test_randomized_farthest_selection_is_reproducible_and_unique():
    embeddings = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.9, 0.1],
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
        ]
    )

    first, similarities = randomized_farthest_indices(
        embeddings, count=4, seed=42, random_pool_size=1
    )
    second, _ = randomized_farthest_indices(
        embeddings, count=4, seed=42, random_pool_size=1
    )

    assert first == second
    assert len(first) == len(set(first)) == 4
    assert similarities[0] is None
    assert all(value is not None for value in similarities[1:])


def test_randomized_farthest_selection_validates_arguments():
    embeddings = np.eye(3)

    with pytest.raises(ValueError):
        randomized_farthest_indices(embeddings, count=4, seed=1)
    with pytest.raises(ValueError):
        randomized_farthest_indices(
            embeddings, count=2, seed=1, random_pool_size=0
        )
