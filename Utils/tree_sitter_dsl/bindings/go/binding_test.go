package tree_sitter_dsl_test

import (
	"testing"

	tree_sitter "github.com/tree-sitter/go-tree-sitter"
	tree_sitter_dsl "github.com/tree-sitter/tree-sitter-dsl/bindings/go"
)

func TestCanLoadGrammar(t *testing.T) {
	language := tree_sitter.NewLanguage(tree_sitter_dsl.Language())
	if language == nil {
		t.Errorf("Error loading Dsl grammar")
	}
}
