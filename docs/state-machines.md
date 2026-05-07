# State Machines

## Access Request

- `submitted`
- `approved`
- `rejected`
- `provisioning`
- `completed`
- `cancelled`

Transitions:

- submit -> `submitted`
- manager approval -> `approved`
- task fan-out -> `provisioning`
- provisioning completion -> `completed`
- rejection/cancel -> terminal

## Provisioning Task

- `pending`
- `in_progress`
- `completed`
- `failed`
- `cancelled`

## Delegation

- `draft`
- `active`
- `expired`
- `revoked`

## Identity

- `active`
- `disabled`
- `terminated`

Emergency termination forces:

- identity -> `terminated`
- open requests -> `cancelled`
- active assignments -> revoked via urgent tasks
