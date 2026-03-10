import 'package:flutter/material.dart';
import 'dashboard.dart';

void main() {
  runApp(AetherionApp());
}

class AetherionApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AETHERION',
      theme: ThemeData.dark(),
      home: Dashboard(),
    );
  }
}
