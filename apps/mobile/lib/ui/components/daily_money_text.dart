// ─── Daily Money Text ──────────────────────────────────────────────
// Formats amounts in COP with tabular figures.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyMoneyText extends StatelessWidget {
  final int amount;
  final bool showSign;
  final TextStyle? style;

  const DailyMoneyText({
    super.key,
    required this.amount,
    this.showSign = false,
    this.style,
  });

  @override
  Widget build(BuildContext context) {
    final text = _formatCOP(amount);
    final color = amount < 0
        ? DailyTokens.error
        : amount > 0
            ? DailyTokens.accent
            : DailyTokens.textPrimary;

    return Text(
      text,
      style: style ?? DailyTokens.moneyNormalTextStyle.copyWith(color: color),
      semanticsLabel: '${showSign && amount >= 0 ? '+' : ''}$text pesos',
    );
  }

  String _formatCOP(int amount) {
    final abs = amount.abs();
    final formatted = abs.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]}.',
    );
    if (amount < 0) return '-$formatted';
    return formatted;
  }
}
