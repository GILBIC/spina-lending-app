import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:image_picker/image_picker.dart';

// Widget tests isolate platform/filesystem work from Flutter's fake clock.
// Real ownership, deletion and restart behavior live in private_image_* tests.
class MemoryPrivateImageStore extends PrivateImageStore {
  @override
  Future<XFile> retain(XFile source) async => source;

  @override
  Future<void> cleanup({String? keepPath}) async {}
}
