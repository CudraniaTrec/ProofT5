import XCTest
import SwiftTreeSitter
import TreeSitterSufu

final class TreeSitterSufuTests: XCTestCase {
    func testCanLoadGrammar() throws {
        let parser = Parser()
        let language = Language(language: tree_sitter_sufu())
        XCTAssertNoThrow(try parser.setLanguage(language),
                         "Error loading Sufu grammar")
    }
}
