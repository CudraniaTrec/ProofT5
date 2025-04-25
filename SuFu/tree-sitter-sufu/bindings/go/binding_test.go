package tree_sitter_sufu_test

import (
	"testing"

	tree_sitter "github.com/tree-sitter/go-tree-sitter"
	tree_sitter_sufu "github.com/tree-sitter/tree-sitter-sufu/bindings/go"
)

func TestCanLoadGrammar(t *testing.T) {
	language := tree_sitter.NewLanguage(tree_sitter_sufu.Language())
	if language == nil {
		t.Errorf("Error loading Sufu grammar")
	}
}
