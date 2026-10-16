import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  final FlutterTts _flutterTts = FlutterTts();

  Future<void> initialize() async {
    await _flutterTts.setLanguage('en-US');
    await _flutterTts.setSpeechRate(1.0);
    await _flutterTts.setVolume(1.0);
    await _flutterTts.setPitch(1.0);
  }

  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    await _flutterTts.speak(text);
  }

  Future<void> pause() async {
    await _flutterTts.pause();
  }

  Future<void> stop() async {
    await _flutterTts.stop();
  }

  Future<void> setRate(double rate) async {
    await _flutterTts.setSpeechRate(rate);
  }

  Future<void> dispose() async {
    await _flutterTts.stop();
  }
}
