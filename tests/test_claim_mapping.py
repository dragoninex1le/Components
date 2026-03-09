"""Tests for ClaimMappingConfig, compiler, and executor."""

import pytest
from porth_common.models.claim_mapping_config import ClaimMappingConfig
from porth_common.services.claim_mapping_compiler import ClaimMappingCompiler, CompilationResult
from porth_common.services.claim_mapping_executor import ClaimMappingExecutor
from porth_common.services.exceptions import CompilationError


class TestClaimMappingConfig:
    """Test ClaimMappingConfig Pydantic model."""

    def test_claim_mapping_config_creation(self):
        """Test creating a ClaimMappingConfig instance."""
        config = ClaimMappingConfig(
            id="config-1",
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            version=1,
            mapping_source={"operations": []},
            compiled_ops=[],
            compiled_hash="hash123",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
            compiled_at="2026-03-09T10:00:00Z",
        )
        assert config.id == "config-1"
        assert config.version == 1
        assert config.compiled_hash == "hash123"


class TestClaimMappingCompiler:
    """Test ClaimMappingCompiler."""

    def test_compile_direct_operation(self):
        """Test compiling a direct mapping operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "direct",
                    "source": "email",
                    "target": "user_email",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert result.compiled_ops is not None
        assert len(result.compiled_ops) == 1
        assert result.compiled_ops[0]["type"] == "direct"

    def test_compile_concat_operation(self):
        """Test compiling a concatenation operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "concat",
                    "sources": ["given_name", "family_name"],
                    "separator": " ",
                    "target": "display_name",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1
        assert result.compiled_ops[0]["type"] == "concat"

    def test_compile_regex_extract_operation(self):
        """Test compiling a regex extraction operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "regex_extract",
                    "source": "email",
                    "pattern": r"(.+)@(.+)",
                    "group": 1,
                    "target": "username",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1

    def test_compile_with_invalid_regex(self):
        """Test that invalid regex is caught during compilation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "regex_extract",
                    "source": "email",
                    "pattern": "(?P<invalid",
                    "group": 1,
                    "target": "username",
                }
            ]
        }
        with pytest.raises(CompilationError):
            compiler.compile(mapping)

    def test_compile_coalesce_operation(self):
        """Test compiling a coalesce operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "coalesce",
                    "sources": ["preferred_username", "email"],
                    "target": "username",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1

    def test_compile_split_operation(self):
        """Test compiling a split operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "split",
                    "source": "name",
                    "delimiter": " ",
                    "index": 0,
                    "target": "first_name",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1

    def test_compile_template_operation(self):
        """Test compiling a template operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "template",
                    "template": "{given_name} {family_name}",
                    "target": "display_name",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1

    def test_compile_lowercase_operation(self):
        """Test compiling a lowercase operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "lowercase",
                    "source": "email",
                    "target": "email",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1

    def test_compile_uppercase_operation(self):
        """Test compiling an uppercase operation."""
        compiler = ClaimMappingCompiler()
        mapping = {
            "operations": [
                {
                    "type": "uppercase",
                    "source": "department",
                    "target": "department",
                }
            ]
        }
        result = compiler.compile(mapping)
        assert len(result.compiled_ops) == 1


class TestClaimMappingExecutor:
    """Test ClaimMappingExecutor."""

    def test_execute_direct_operation(self):
        """Test executing a direct operation."""
        executor = ClaimMappingExecutor()
        ops = [
            {
                "type": "direct",
                "source": "email",
                "target": "user_email",
            }
        ]
        jwt_claims = {"email": "john@example.com"}
        result = executor.execute(ops, jwt_claims)
        assert result["user_email"] == "john@example.com"

    def test_execute_concat_operation(self):
        """Test executing a concatenation."""
        executor = ClaimMappingExecutor()
        ops = [
            {
                "type": "concat",
                "sources": ["first_name", "last_name"],
                "separator": " ",
                "target": "display_name",
            }
        ]
        jwt_claims = {"first_name": "John", "last_name": "Doe"}
        result = executor.execute(ops, jwt_claims)
        assert result["display_name"] == "John Doe"

    def test_execute_lowercase_operation(self):
        """Test executing a lowercase operation."""
        executor = ClaimMappingExecutor()
        ops = [
            {
                "type": "lowercase",
                "source": "email",
                "target": "email_lower",
            }
        ]
        jwt_claims = {"email": "JOHN@EXAMPLE.COM"}
        result = executor.execute(ops, jwt_claims)
        assert result["email_lower"] == "john@example.com"

    def test_execute_with_missing_source(self):
        """Test graceful handling of missing source field."""
        executor = ClaimMappingExecutor()
        ops = [
            {
                "type": "direct",
                "source": "missing_field",
                "target": "output",
            }
        ]
        jwt_claims = {"email": "john@example.com"}
        result = executor.execute(ops, jwt_claims)
        # Missing field should be skipped gracefully
        assert "output" not in result
