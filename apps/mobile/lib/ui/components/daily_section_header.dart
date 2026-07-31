// ─── Daily Section Header ──────────────────────────────────────────

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailySectionHeader extends StatelessWidget {
  final String title;

  const DailySectionHeader({super.key, required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: DailyTokens.shapeSM),
      child: Row(
        children: [
          Container(
            width: 3, height: 18,
            decoration: BoxDecoration(
              color: DailyTokens.accent,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            title,
            style: const TextStyle(
              fontSize: 16, fontWeight: FontWeight.w600,
              color: DailyTokens.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
