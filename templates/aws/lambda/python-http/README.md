# AWS / Lambda / Python

Infrastructure candidates: Terraform, AWS CDK Python and AWS CDK TypeScript.
No public function URL is created. Invoke through the authenticated Lambda API.
All variants require an explicit account, region, immutable revision and environment purpose.
Production uses managed multi-zone Lambda and preserves log groups on removal.

These sources have not been certified by a cloud deployment. Native pipeline integration,
complete cost coverage (logs, transfer, state storage), and governed lifecycle execution
must be completed before registering these as deployable catalog variants.
Terraform requires a separately configured encrypted S3 backend with state locking.
CDK requires a separately approved bootstrap; synthesis does not bootstrap the account.
