// ─── Daily App Scaffold ────────────────────────────────────────────
// Base scaffold with SafeArea, consistent padding, and offline indicator.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyAppScaffold extends StatelessWidget {
  final Widget body;
  final String? title;
  final Widget? leading;
  final List<Widget>? actions;
  final bool showAppBar;
  final Widget? bottomNavigationBar;
  final bool extendBodyBehindAppBar;

  const DailyAppScaffold({
    super.key,
    required this.body,
    this.title,
    this.leading,
    this.actions,
    this.showAppBar = true,
    this.bottomNavigationBar,
    this.extendBodyBehindAppBar = false,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: showAppBar ? AppBar(
        title: title != null ? Text(title!) : null,
        leading: leading,
        actions: actions,
        centerTitle: true,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: DailyTokens.surface,
        foregroundColor: DailyTokens.textPrimary,
      ) : null,
      body: SafeArea(
        child: extendBodyBehindAppBar ? body : Padding(
          padding: const EdgeInsets.symmetric(horizontal: DailyTokens.shapeLG),
          child: body,
        ),
      ),
      bottomNavigationBar: bottomNavigationBar,
    );
  }
}
