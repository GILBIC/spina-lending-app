import assert from 'node:assert/strict';
import test from 'node:test';

import {
  clientNotificationRows,
  requestClientNotificationRead,
} from '../assets/roles/client.js';

test('Client Web updates distinguish unread from read and only unread can be marked read', () => {
  const html = clientNotificationRows([
    {
      notification_id: 'note-unread',
      title: 'Payment posted',
      message: 'Receipt R-1001 was posted.',
      created_at: '2026-09-13T01:00:00Z',
      is_read: false,
    },
    {
      notification_id: 'note-read',
      title: 'Renewal reviewed',
      message: 'Management reviewed your renewal.',
      created_at: '2026-09-13T02:00:00Z',
      is_read: true,
    },
  ]);

  assert.match(html, />Unread</);
  assert.match(html, />Read</);
  assert.match(html, /data-client-notification-read="note-unread"/);
  assert.doesNotMatch(html, /data-client-notification-read="note-read"/);
});

test('Client Web mark-read uses the protected recipient-scoped endpoint', async () => {
  const calls = [];
  const api = {
    async request(path, options) {
      calls.push({ path, options });
      return { notification_id: 'note-1', is_read: true };
    },
  };

  const result = await requestClientNotificationRead({
    api,
    notificationId: 'note/1',
  });

  assert.deepEqual(calls, [
    {
      path: '/api/v1/activity-notifications/note%2F1/read',
      options: { method: 'POST' },
    },
  ]);
  assert.equal(result.is_read, true);
});
