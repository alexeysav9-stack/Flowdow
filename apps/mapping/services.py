"""Validation service for mapping configurations."""


class MappingValidationService:
    """Verifies whether mapping rules satisfy template placeholder requirements."""

    @classmethod
    def validate_rules(
        cls,
        template_variables: list[str],
        mapping_rules: dict[str, dict],
        data_columns: list[str],
    ) -> tuple[bool, list[str]]:
        """Checks for missing required variables or invalid column targets.

        Returns (is_valid, list_of_error_messages).
        """
        errors = []
        available_columns = set(data_columns)

        for var in template_variables:
            rule = mapping_rules.get(var)
            if not rule:
                errors.append(f"Variable '{var}' has no assigned mapping rule.")
                continue

            target_col = rule.get("column")
            default_val = rule.get("default")
            is_required = rule.get("required", True)

            if target_col and target_col not in available_columns:
                errors.append(f"Variable '{var}' maps to unknown column '{target_col}'.")
            elif not target_col and not default_val and is_required:
                errors.append(
                    f"Required variable '{var}' has neither a column mapping nor a default value."
                )

        return len(errors) == 0, errors
