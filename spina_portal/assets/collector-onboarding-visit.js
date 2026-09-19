import { mountOnboardingCase } from './office-onboarding.js';

export function mountCollectorOnboardingVisit(options) {
  return mountOnboardingCase({ ...options, collector: true });
}
