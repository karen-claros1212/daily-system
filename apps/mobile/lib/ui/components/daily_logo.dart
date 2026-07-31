// ─── Daily Logo Component ─────────────────────────────────────────
// Simple vector-style logo: a route line forming a "D" shape with nodes.
// No external images — pure Flutter drawing.

import 'package:flutter/material.dart';
import '../../theme/generated/daily_tokens.dart';

class DailyLogo extends StatelessWidget {
  final double size;
  final Color? color;

  const DailyLogo({
    super.key,
    this.size = 40,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = color ?? DailyTokens.primary;
    // ExcludeSemantics: "Daily System" text is adjacent and serves as the semantic label
    return ExcludeSemantics(
      child: CustomPaint(
        size: Size(size, size),
        painter: _DailyLogoPainter(color: c),
        key: key,
      ),
    );
  }
}

class _DailyLogoPainter extends CustomPainter {
  final Color color;
  _DailyLogoPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.12
      ..strokeCap = StrokeCap.round;

    final w = size.width;
    final h = size.height;
    final cx = w * 0.35;

    // Vertical stem of D
    canvas.drawLine(
      Offset(cx, h * 0.15),
      Offset(cx, h * 0.85),
      paint,
    );

    // Curved right side of D
    final path = Path();
    path.moveTo(cx, h * 0.15);
    path.cubicTo(
      w * 0.9, h * 0.15,
      w * 0.95, h * 0.5,
      w * 0.9, h * 0.85,
    );
    path.cubicTo(
      w * 0.75, h * 0.95,
      cx, h * 0.95,
      cx, h * 0.85,
    );
    canvas.drawPath(path, paint);

    // Route nodes
    final nodePaint = Paint()..color = color;
    final nodeRadius = w * 0.04;
    
    // Node at top
    canvas.drawCircle(Offset(cx, h * 0.15), nodeRadius, nodePaint);
    // Node at middle (check point)
    canvas.drawCircle(Offset(w * 0.7, h * 0.5), nodeRadius, nodePaint);
    // Node at bottom
    canvas.drawCircle(Offset(cx, h * 0.85), nodeRadius, nodePaint);

    // Small check mark at middle node
    final checkPaint = Paint()
      ..color = DailyTokens.accent
      ..style = PaintingStyle.stroke
      ..strokeWidth = w * 0.06
      ..strokeCap = StrokeCap.round;
    final checkCx = w * 0.7;
    final checkCy = h * 0.5;
    canvas.drawLine(
      Offset(checkCx - w * 0.06, checkCy),
      Offset(checkCx - w * 0.02, checkCy + w * 0.06),
      checkPaint,
    );
    canvas.drawLine(
      Offset(checkCx - w * 0.02, checkCy + w * 0.06),
      Offset(checkCx + w * 0.06, checkCy - w * 0.06),
      checkPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _DailyLogoPainter oldDelegate) =>
      color != oldDelegate.color;
}
