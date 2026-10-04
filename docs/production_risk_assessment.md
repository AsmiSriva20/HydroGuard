# Deployment Notes

HydroGuard is currently a prototype.

These are some of the issues that would need more work before using the system in a real environment.

## Sensors

Possible problems:

- flow readings can drift without calibration
- FC-37 can react to splashes or cleaning water
- presence detection depends on sensor placement
- failed devices can stop sending data

Current or possible controls:

- combined-sensor rules
- device offline detection
- per-device calibration
- testing in different environments

## Alerts

Possible problems:

- cleaning activity can look similar to a leak
- a low-flow leak may not trigger the flow sensor
- one fixed threshold may not work for every location

Possible improvements:

- configurable thresholds
- operator identity and acknowledgement audit history
- false-positive review
- anomaly detection after enough labelled data is collected

## Security

The hosted demo keeps its admin key on the server. Public demo actions are limited to one configured device and six predefined scenarios.

A real deployment would still need:

- authenticated MQTT connections
- topic-level access control
- HTTPS
- user accounts
- role-based access
- audit logs
- managed secret storage

## Data

A longer-running deployment would also need:

- data retention rules
- database backups
- restore testing
- API and broker monitoring
- retry handling for temporary outages