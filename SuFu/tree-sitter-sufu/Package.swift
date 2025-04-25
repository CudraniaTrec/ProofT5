// swift-tools-version:5.3
import PackageDescription

let package = Package(
    name: "TreeSitterSufu",
    products: [
        .library(name: "TreeSitterSufu", targets: ["TreeSitterSufu"]),
    ],
    dependencies: [
        .package(url: "https://github.com/ChimeHQ/SwiftTreeSitter", from: "0.8.0"),
    ],
    targets: [
        .target(
            name: "TreeSitterSufu",
            dependencies: [],
            path: ".",
            sources: [
                "src/parser.c",
                // NOTE: if your language has an external scanner, add it here.
            ],
            resources: [
                .copy("queries")
            ],
            publicHeadersPath: "bindings/swift",
            cSettings: [.headerSearchPath("src")]
        ),
        .testTarget(
            name: "TreeSitterSufuTests",
            dependencies: [
                "SwiftTreeSitter",
                "TreeSitterSufu",
            ],
            path: "bindings/swift/TreeSitterSufuTests"
        )
    ],
    cLanguageStandard: .c11
)
