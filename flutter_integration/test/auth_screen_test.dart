import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:royal_pro_flutter/screens/auth_screen.dart';

void main() {
  testWidgets('login rejects empty credentials before making an API request',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.byType(FilledButton));
    await tester.pump();

    expect(find.text('Please enter a username.'), findsOneWidget);
    expect(find.text('Please enter your password.'), findsOneWidget);
  });

  testWidgets('registration requires an email address', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.text('Sign Up'));
    await tester.pump();
    await tester.tap(find.byType(FilledButton));
    await tester.pump();

    expect(find.text('Please enter your email.'), findsOneWidget);
  });
}
