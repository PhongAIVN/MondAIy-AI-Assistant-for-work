import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { watchForAppUpdate } from '../src/lib/appUpdateNotice.ts';

type FakeWorker = EventTarget & { state: ServiceWorkerState };

const makeWorker = (state: ServiceWorkerState): FakeWorker => {
  const worker = new EventTarget() as FakeWorker;
  worker.state = state;
  return worker;
};

const makeServiceWorker = (worker: FakeWorker | null, waiting: FakeWorker | null = null) => {
  const registration = new EventTarget() as ServiceWorkerRegistration;
  Object.defineProperties(registration, {
    installing: { configurable: true, get: () => worker },
    waiting: { configurable: true, get: () => waiting },
  });

  const serviceWorker = {
    controller: worker,
    getRegistration: async () => registration,
  } as unknown as ServiceWorkerContainer;

  return { registration, serviceWorker };
};

describe('watchForAppUpdate', () => {
  it('notifies when an existing app receives an installed Service Worker update', async () => {
    const worker = makeWorker('installing');
    const { serviceWorker } = makeServiceWorker(worker);
    let updateCount = 0;
    const onUpdate = () => {
      updateCount += 1;
    };
    const stopWatching = watchForAppUpdate(serviceWorker, onUpdate);

    await Promise.resolve();
    worker.state = 'installed';
    worker.dispatchEvent(new Event('statechange'));

    assert.equal(updateCount, 1);
    stopWatching();
  });

  it('does not notify on the first Service Worker install', async () => {
    const worker = makeWorker('installing');
    const { serviceWorker } = makeServiceWorker(worker);
    Object.defineProperty(serviceWorker, 'controller', { configurable: true, value: null });
    let updateCount = 0;
    const onUpdate = () => {
      updateCount += 1;
    };
    watchForAppUpdate(serviceWorker, onUpdate);

    await Promise.resolve();
    worker.state = 'installed';
    worker.dispatchEvent(new Event('statechange'));

    assert.equal(updateCount, 0);
  });
});
