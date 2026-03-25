import AppKit
import Foundation
import Vision

struct RecognitionResult: Codable {
    let text: String
    let minX: Double
    let minY: Double
    let maxX: Double
    let maxY: Double
}

enum OCRScriptError: Error {
    case missingImagePath
    case unreadableImage
    case unreadableCGImage
}

func loadImage(from path: String) throws -> CGImage {
    let imageURL = URL(fileURLWithPath: path)
    guard let image = NSImage(contentsOf: imageURL) else {
        throw OCRScriptError.unreadableImage
    }

    guard
        let tiffData = image.tiffRepresentation,
        let bitmap = NSBitmapImageRep(data: tiffData),
        let cgImage = bitmap.cgImage
    else {
        throw OCRScriptError.unreadableCGImage
    }

    return cgImage
}

let arguments = CommandLine.arguments
guard arguments.count >= 2 else {
    throw OCRScriptError.missingImagePath
}

let imagePath = arguments[1]
let image = try loadImage(from: imagePath)

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: image, options: [:])
try handler.perform([request])

let observations = request.results ?? []
let recognitions = observations.compactMap { observation -> RecognitionResult? in
    guard let candidate = observation.topCandidates(1).first else {
        return nil
    }

    let text = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !text.isEmpty else {
        return nil
    }

    let box = observation.boundingBox
    return RecognitionResult(
        text: text,
        minX: Double(box.minX),
        minY: Double(box.minY),
        maxX: Double(box.maxX),
        maxY: Double(box.maxY)
    )
}

let data = try JSONEncoder().encode(recognitions)
FileHandle.standardOutput.write(data)
