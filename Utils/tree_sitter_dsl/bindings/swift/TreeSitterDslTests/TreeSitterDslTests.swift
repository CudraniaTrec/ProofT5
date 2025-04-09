import XCTest
import SwiftTreeSitter
import TreeSitterDsl

final class TreeSitterDslTests: XCTestCase {
    func testCanLoadGrammar() throws {
        let parser = Parser()
        let language = Language(language: tree_sitter_dsl())
        XCTAssertNoThrow(try parser.setLanguage(language),
                         "Error loading Dsl grammar")
    }
}
