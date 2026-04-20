from __future__ import annotations

from math import isfinite
from typing import Any, Sequence

from ..contracts import BasketItem
from ..interfaces.basket_validator import BasketValidator
from ..serialization import validate_output_document as validate_serialized_output


class DefaultBasketValidator(BasketValidator):
    def validate(
        self, baskets: Sequence[BasketItem], config: Any | None = None
    ) -> None:
        for basket in baskets:
            if not basket.token_ids:
                raise ValueError(f"basket {basket.basket_id} has no token ids")
            
            normalized_token_ids = self._normalize_required_strings(
                basket.token_ids, f"basket {basket.basket_id} has invalid token ids"
            )

            if len(set(normalized_token_ids)) != len(normalized_token_ids):
                raise ValueError(f"basket {basket.basket_id} has duplicate token ids")
            
            if not basket.dependency_basis:
                raise ValueError(
                    f"basket {basket.basket_id} dependency_basis must not be empty"
                )
            
            normalized_dependency_basis = self._normalize_required_strings(
                basket.dependency_basis,
                f"basket {basket.basket_id} has invalid dependency basis",
            )

            if len(set(normalized_dependency_basis)) != len(
                normalized_dependency_basis
            ):
                raise ValueError(
                    f"basket {basket.basket_id} has duplicate dependency basis entries"
                )
            
            if not isfinite(basket.expected_sum) or basket.expected_sum <= 0:
                raise ValueError(f"basket {basket.basket_id} expected_sum must be > 0")

    @staticmethod
    def _normalize_required_strings(
        values: Sequence[str], error_message: str
    ) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError(error_message)
            
            cleaned = value.strip()

            if not cleaned:
                raise ValueError(error_message)
            
            normalized.append(cleaned)
            
        return normalized


def validate_output_document(payload: dict[str, Any]) -> None:
    """Compatibility wrapper around schema-backed validation."""
    validate_serialized_output(payload)
