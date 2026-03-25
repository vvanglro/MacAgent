import CoreGraphics
import Foundation

enum MouseClickError: Error {
    case missingCoordinates
    case invalidCoordinates
}

let arguments = CommandLine.arguments
guard arguments.count >= 3 else {
    throw MouseClickError.missingCoordinates
}

guard
    let x = Double(arguments[1]),
    let y = Double(arguments[2])
else {
    throw MouseClickError.invalidCoordinates
}

let point = CGPoint(x: x, y: y)

let move = CGEvent(
    mouseEventSource: nil,
    mouseType: .mouseMoved,
    mouseCursorPosition: point,
    mouseButton: .left
)
move?.post(tap: .cghidEventTap)

usleep(50_000)

let down = CGEvent(
    mouseEventSource: nil,
    mouseType: .leftMouseDown,
    mouseCursorPosition: point,
    mouseButton: .left
)
down?.post(tap: .cghidEventTap)

usleep(50_000)

let up = CGEvent(
    mouseEventSource: nil,
    mouseType: .leftMouseUp,
    mouseCursorPosition: point,
    mouseButton: .left
)
up?.post(tap: .cghidEventTap)
