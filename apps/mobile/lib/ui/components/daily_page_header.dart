// ─── Daily Page Header ─────────────────────────────────────────────

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyPageHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? leading;
  final List<Widget>? actions;

  const DailyPageHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.actions,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: DailyTokens.shapeLG, vertical: DailyTokens.shapeMD),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (leading != null) ...[
                leading!,
                const SizedBox(width: DailyTokens.shapeSM),
              ],
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 24, fontWeight: FontWeight.w700,
                    color: DailyTokens.textPrimary,
                  ),
                ),
              ),
              if (actions != null) ...actions!,
            ],
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(
              subtitle!,
              style: const TextStyle(fontSize: 14, color: DailyTokens.outlineVariant),
            ),
          ],
        ],
      ),
    );
  }
}
