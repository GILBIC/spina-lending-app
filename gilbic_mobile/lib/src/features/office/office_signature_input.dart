import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

/// Finger/stylus signature held only in this signing view's memory.
class OfficeSignatureInput extends StatefulWidget {
  const OfficeSignatureInput({
    required this.enabled,
    required this.onChanged,
    super.key,
  });
  final bool enabled;
  final ValueChanged<OfficePhoto?> onChanged;
  @override
  State<OfficeSignatureInput> createState() => _OfficeSignatureInputState();
}

class _OfficeSignatureInputState extends State<OfficeSignatureInput>
    with AutomaticKeepAliveClientMixin<OfficeSignatureInput> {
  @override
  bool get wantKeepAlive => true;
  final strokes = <List<Offset>>[];
  List<Offset>? active;
  int revision = 0;
  String status = 'Sign in the box using your finger or a stylus.';
  void _changed() {
    revision++;
    widget.onChanged(null);
  }

  Offset _point(Offset point, double width) => Offset(
    (point.dx / width * 960).clamp(0, 960),
    (point.dy / width * 960).clamp(0, 480),
  );
  void _start(Offset point, double width) {
    if (!widget.enabled) return;
    _changed();
    setState(() {
      active = [_point(point, width)];
      strokes.add(active!);
      status = 'Signing…';
    });
  }

  void _move(Offset point, double width) {
    if (!widget.enabled || active == null || active!.length >= 10000) return;
    setState(() => active!.add(_point(point, width)));
  }

  void _cancel() {
    if (active == null) return;
    _changed();
    setState(() {
      strokes.remove(active);
      active = null;
      status = 'Drawing interrupted. Check the signature and draw again.';
    });
  }

  Future<void> _finish() async {
    if (active == null) return;
    active = null;
    final generation = revision;
    final enough = strokes.any((stroke) {
      var distance = 0.0;
      for (var i = 1; i < stroke.length; i++) {
        distance += (stroke[i] - stroke[i - 1]).distance;
      }
      return distance >= 12;
    });
    if (!enough) {
      setState(() => status = 'Draw your signature before saving.');
      return;
    }
    ui.Picture? picture;
    ui.Image? image;
    try {
      final recorder = ui.PictureRecorder();
      _SignaturePainter(strokes).paint(Canvas(recorder), const Size(960, 480));
      picture = recorder.endRecording();
      image = await picture.toImage(960, 480);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      if (!mounted || generation != revision || active != null) return;
      if (bytes == null) throw StateError('No PNG');
      setState(() => status = 'Signature ready. Check it before saving.');
      widget.onChanged(
        OfficePhoto(
          bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes),
          'image/png',
        ),
      );
    } on Object {
      if (mounted && generation == revision) {
        setState(
          () => status =
              'Could not prepare the signature. Draw again or upload signed paper.',
        );
      }
    } finally {
      image?.dispose();
      picture?.dispose();
    }
  }

  void _clear() {
    if (!widget.enabled) return;
    _changed();
    setState(() {
      active = null;
      strokes.clear();
      status = 'Signature cleared. The applicant can sign again.';
    });
  }

  @override
  void dispose() {
    revision++;
    active = null;
    strokes.clear();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'Applicant: review the saved information above, then sign in the box.',
        ),
        const SizedBox(height: 8),
        LayoutBuilder(
          builder: (context, constraints) => Semantics(
            label:
                'Applicant signature drawing area. Use Upload signed paper if drawing is unavailable.',
            child: AspectRatio(
              aspectRatio: 2,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.black87, width: 2),
                ),
                child: GestureDetector(
                  key: const Key('office-signature-pad'),
                  behavior: HitTestBehavior.opaque,
                  onPanStart: widget.enabled
                      ? (event) =>
                            _start(event.localPosition, constraints.maxWidth)
                      : null,
                  onPanUpdate: widget.enabled
                      ? (event) =>
                            _move(event.localPosition, constraints.maxWidth)
                      : null,
                  onPanEnd: widget.enabled ? (_) => _finish() : null,
                  onPanCancel: widget.enabled ? _cancel : null,
                  child: CustomPaint(painter: _SignaturePainter(strokes)),
                ),
              ),
            ),
          ),
        ),
        Text(status),
        officeButton('Clear signature', widget.enabled ? _clear : null),
      ],
    );
  }
}

class _SignaturePainter extends CustomPainter {
  const _SignaturePainter(this.strokes);
  final List<List<Offset>> strokes;
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.white);
    canvas.save();
    canvas.scale(size.width / 960, size.height / 480);
    final ink = Paint()
      ..color = const Color(0xff171717)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    for (final stroke in strokes) {
      if (stroke.length < 2) continue;
      final path = Path()..moveTo(stroke.first.dx, stroke.first.dy);
      for (final point in stroke.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      canvas.drawPath(path, ink);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _SignaturePainter oldDelegate) => true;
}
