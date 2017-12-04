# Examples

All presented below examples can be run on previously created Kubernetes Cluster (or single Node + Master).   
To setup such cluster you should use this blueprint: https://github.com/cloudify-examples/simple-kubernetes-blueprint/tree/4.0.1


### Simple example

*simple-example-blueprint.yaml*

TODO

### Replicasets

*replicasets-example-blueprint.yaml*

TODO

### Persistent volumes

*persistent_volumes-example-blueprint*

TODO

### Service chaining

There are 3 blueprints defined as examples of container-based service chaining for kubernetes.
These scenarios are using Linux bridging and static routing to provide chain connectivity between separate pods.
Implementations of all scenarios are done using utilities-plugin.
Separate generic blueprint *vnf-blueprint* is used to define each pod and network interfaces by *service_chain* deployment.
In other words main (*service_chain*) deployment is creating separate deployments from *vnf-blueprint* for each pod using utilities-plugin.
  
So, before start you need to upload *vnf-blueprint* to Cloudify Manager. You can do it by:

```
cfy blueprints upload vnf-blueprint.yaml -b service_chain_vnf_component
```

It is also need to upload wagons for plugins used in blueprints:

```
cfy plugins upload https://github.com/cloudify-incubator/cloudify-utilities-plugin/releases/download/1.2.5/cloudify_utilities_plugin-1.2.5-py27-none-linux_x86_64-centos-Core.wgn
cfy plugins upload https://github.com/cloudify-incubator/cloudify-kubernetes-plugin/releases/download/1.0.0/cloudify_kubernetes_plugin-1.0.0-py27-none-linux_x86_64.wgn
cfy plugins upload http://repository.cloudifysource.org/cloudify/wagons/cloudify-fabric-plugin/1.5/cloudify_fabric_plugin-1.5-py27-none-linux_x86_64-centos-Core.wgn

```

Last step before making a deployments is to provide Kubernetes API credentials as a secrets.
Using this approach the will be reusable for all deployments.
You can do it executing:

```
cfy secrets create kubernetes_master_ip -s [IP ADDRESS OF KUBERNETES API]
cfy secrets create kubernetes_master_user -s [SSH USERNAME FOR KUBERNETES MASTER]
cfy secrets create kubernetes_master_ssh_key_path -s  [SSH KEY FILE PATH FOR KUBERNETES MASTER]
```


#### Example 1

*service_chain_1-example-blueprint.yaml*

Use case deploys chain with 3 containers:
* client
* VNF (router)
* server

![sfc_uc1](https://user-images.githubusercontent.com/20417307/28112813-b29b6a5c-66fa-11e7-8ecd-8c219a984412.jpg)

You can deploy it executing:

```
cfy install -b service_chain_1 service_chain_1-example-blueprint.yaml
```

You can verify if this setup has been deployed correctly on Kuberentes VM using command line:

1.  Check if all pod has been created. Execute:

*kubectl get pods*

You should see 3 pods. All have to be in 'Running' state:

```
NAME           READY     STATUS    RESTARTS   AGE
client         1/1       Running   0          2m
router         1/1       Running   0          2m
server         1/1       Running   0          1m
```

2. Attach to 'client' console:

*kubectl attach client -it*

3. Perform tests for server connectivity ping ICMP traffic should pass

*ping 192.168.1.7*

4. Try to establish a ssh session. You should have possibility of making a connection.

*ssh test@192.168.1.7*

password: *test*

5. Check if HTTP server is responding.

*curl 192.168.1.7:8080*

HTTP traffic should pass. A standard python SimpleHTTPServer directory listing should be present.

*curl 192.168.1.7:8080/?q=banned*

Expected 404 error.


#### Example 2

*service_chain_2-example-blueprint.yaml*

Use case deploys chain with 4 containers:
* client
* VNF (router)
* VNF (firewall)
* server

![sfc_uc2](https://user-images.githubusercontent.com/20417307/28112823-b7632502-66fa-11e7-9851-0bdc96017a4a.jpg)

You can deploy it executing:

```
cfy install -b service_chain_2 service_chain_2-example-blueprint.yaml
```

You can verify if this setup has been deployed correctly on Kuberentes VM using command line:

1.  Check if all pod has been created. Execute:

*kubectl get pods*

You should see 4 pods. All have to be in 'Running' state:

```
NAME           READY     STATUS    RESTARTS   AGE
client         1/1       Running   0          2m
router         1/1       Running   0          2m
firewall       1/1       Running   0          2m
server         1/1       Running   0          1m
```

2. Attach to 'client' console:

*kubectl attach client -it*

3. Perform tests for server connectivity ping ICMP traffic should pass

*ping 192.168.1.7*

4. Try to establish a ssh session. 
TCP SSH traffic should be blocked by firewall.
Making new connection should be impossible.

*ssh test@192.168.1.7*

5. Check if HTTP server is responding.

*curl 192.168.1.7:8080*

HTTP traffic should pass. A standard python SimpleHTTPServer directory listing should be present.

*curl 192.168.1.7:8080/?q=banned*

Expected 404 error.


#### Example 3

*service_chain_3-example-blueprint.yaml*

Use case deploys chain with 5 containers:
* client
* VNF (router)
* VNF (firewall)
* VNF (URL filter)
* server

![sfc_uc3](https://user-images.githubusercontent.com/20417307/28112833-be9eb232-66fa-11e7-8ab5-dbdca51bda99.jpg)

You can deploy it executing:

```
cfy install -b service_chain_3 service_chain_3-example-blueprint.yaml
```

You can verify if this setup has been deployed correctly on Kuberentes VM using command line:

1.  Check if all pod has been created. Execute:

*kubectl get pods*

You should see 5 pods. All have to be in 'Running' state:

```
NAME           READY     STATUS    RESTARTS   AGE
client         1/1       Running   0          2m
router         1/1       Running   0          2m
firewall       1/1       Running   0          2m
filter         1/1       Running   0          2m
server         1/1       Running   0          1m
```

2. Attach to 'client' console:

*kubectl attach client -it*

3. Perform tests for server connectivity ping ICMP traffic should pass

*ping 192.168.1.7*

4. Try to establish a ssh session. 
TCP SSH traffic should be blocked by firewall.
Making new connection should be impossible.

*ssh test@192.168.1.7*

5. Check if HTTP server is responding.

*curl 192.168.1.7:8080*

HTTP traffic should pass. A standard python SimpleHTTPServer directory listing should be present.

*curl 192.168.1.7:8080/?q=banned*

HTTP traffic should pass. A web page with information about a banned request is displayed
