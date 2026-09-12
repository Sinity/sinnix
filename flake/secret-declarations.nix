# Pure evaluations have no private inputs. Live activation wrappers pass the
# existing agenix declaration manifest through this narrow impure seam.
{
  manifestPath ? builtins.getEnv "SINNIX_SECRET_DECLARATIONS",
}:
if manifestPath == "" then
  { }
else
  let
    declarations = import manifestPath;
  in
  if builtins.isAttrs declarations then
    declarations
  else
    throw "SINNIX_SECRET_DECLARATIONS must evaluate to an attribute set"
