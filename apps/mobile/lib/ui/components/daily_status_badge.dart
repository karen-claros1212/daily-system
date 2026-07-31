// ─── Daily Status Badge ────────────────────────────────────────────
// Color + icon + text status indicator. Never color only.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

enum DailyStatusType {
  success(label: 'Correcto', icon: Icons.check_circle, color: DailyTokens.accent),
  warning(label: 'Advertencia', icon: Icons.warning_amber, color: DailyTokens.warning),
  error(label: 'Error', icon: Icons.error, color: DailyTokens.error),
  info(label: 'Información', icon: Icons.info, color: DailyTokens.primary),
  neutral(label: 'Normal', icon: Icons.circle, color: DailyTokens.outlineVariant);

  final String label;
  final IconData icon;
  final Color color;
  const DailyStatusType({required this.label, required this.icon, required this.color});
}

class DailyStatusBadge extends StatelessWidget {
  final DailyStatusType type;
  final String? text;
  final bool compact;

  const DailyStatusBadge({
    super.key,
    required this.type,
    this.text,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final bgColor = type.color.withValues(alpha: 0.12);
    final content = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(type.icon, size: compact ? 16 : 18, color: type.color),
        const SizedBox(width: 6),
        Text(
          text ?? type.label,
          style: TextStyle(
            fontSize: compact ? 11 : 12,
            fontWeight: FontWeight.w600,
            color: type.color,
          ),
        ),
      ],
    );

    if (compact) {
      return content;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(DailyTokens.shapeSM),
      ),
      child: content,
    );
  }
}
