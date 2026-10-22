import Foundation
import Vision
import AppKit
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ru-RU", "en-US"]
request.usesLanguageCorrection = true
if CommandLine.arguments.count < 2 { fatalError("image path required") }
let url=URL(fileURLWithPath: CommandLine.arguments[1])
let handler=VNImageRequestHandler(url:url,options:[:])
do {
 try handler.perform([request])
 for item in request.results ?? [] {
  if let line=item.topCandidates(1).first { print(line.string) }
 }
} catch { fputs("OCR failed: \(error)\n",stderr);exit(1) }
